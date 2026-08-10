"""Coverage wave 26 — core/entity_type_service remaining branches (TDD).

Picks up where wave 22 left off (entity_type_service 78% -> 90%+):

- merge_entity_types: metadata_json None init + merge history append, commit error
- create_entity_type: invalid slug, invalid schema, duplicate slug, commit error
- get_entity_type: no-id+no-slug ValueError, include_inactive=True, not-found
- list_entity_types: is_active=None (all), include_system=True, search filter,
  default limit/offset wiring
- update_entity_type: not-found, system-type block, snapshot+invalidate+version
  bump, field updates without schema, commit error
- delete_entity_type: not-found False, soft delete, hard delete, commit errors
- count_entity_types: include_system variants
- compare_schema_versions: required-property removal (critical), optional removal
  (info), property type change (warning), required add
- close() with unowned session
"""
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Session

from core.entity_type_service import EntityTypeService
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
        id="et-1",
        tenant_id="t1",
        slug="customer",
        display_name="Customer",
        json_schema={"type": "object", "properties": {"name": {"type": "string"}}},
        is_system=False,
        is_active=True,
        version=1,
        metadata_json={},
        available_skills=None,
        description=None,
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


class TestMergeExtras:
    def test_merge_metadata_none_init_and_commit_error(self, service):
        source = _etype(id="src", slug="lead")
        target = _etype(id="tgt", slug="customer", metadata_json=None)
        _chain(service.db, first_result=None)
        service.db.query.return_value.filter.return_value.first.side_effect = [source, target]
        service.db.query.return_value.filter.return_value.update.return_value = 2
        service.db.commit.side_effect = RuntimeError("commit boom")
        with pytest.raises(RuntimeError):
            service.merge_entity_types("t1", source_id="src", target_slug="customer")
        assert service.db.rollback.called
        # metadata was initialized + merge entry appended before the commit failed
        assert len(target.metadata_json["merges"]) == 1

    def test_merge_appends_history(self, service):
        source = _etype(id="src", slug="lead")
        target = _etype(id="tgt", slug="customer", metadata_json={"merges": [{"at": "old"}]})
        _chain(service.db, first_result=None)
        service.db.query.return_value.filter.return_value.first.side_effect = [source, target]
        service.db.query.return_value.filter.return_value.update.return_value = 2
        result = service.merge_entity_types(
            "t1", source_id="src", target_slug="customer", workspace_id="ws-9"
        )
        assert result is True
        assert len(target.metadata_json["merges"]) == 2
        assert service.db.commit.called
        ws_call = service.db.query.return_value.filter.return_value.filter.call_args
        assert ws_call is not None

    def test_merge_workspace_filter_not_applied(self, service):
        source = _etype(id="src", slug="lead")
        target = _etype(id="tgt", slug="customer")
        _chain(service.db, first_result=None)
        service.db.query.return_value.filter.return_value.first.side_effect = [source, target]
        service.db.query.return_value.filter.return_value.update.return_value = 1
        service.merge_entity_types("t1", source_id="src", target_slug="customer")
        filter_calls = service.db.query.return_value.filter.call_args_list
        assert not any("workspace_id" in str(a) for a in filter_calls)


class TestCreate:
    def test_create_invalid_slug(self, service):
        with pytest.raises(ValueError, match="Invalid slug"):
            service.create_entity_type("t1", "bad slug!", "Bad", json_schema={"type": "object"})

    def test_create_invalid_schema(self, service):
        service.validator.validate_schema.return_value = (False, "not draft-2020-12")
        with pytest.raises(ValueError, match="Invalid JSON Schema"):
            service.create_entity_type("t1", "customer", "Customer", json_schema={"bad": True})

    def test_create_duplicate(self, service):
        _chain(service.db, first_result=_etype())
        with pytest.raises(ValueError, match="already exists"):
            service.create_entity_type("t1", "customer", "Customer", json_schema={"type": "object"})

    def test_create_commit_error(self, service):
        _chain(service.db, first_result=None)
        service.db.commit.side_effect = RuntimeError("boom")
        with pytest.raises(RuntimeError):
            service.create_entity_type("t1", "customer", "Customer", json_schema={"type": "object"})
        assert service.db.rollback.called

    def test_create_success_system_flag(self, service):
        _chain(service.db, first_result=None)
        et = service.create_entity_type(
            "t1", "customer", "Customer", json_schema={"type": "object"},
            available_skills=["skill-a"], is_system=True, is_active=False,
        )
        assert et.id
        assert et.version == 1
        assert et.is_system is True
        assert et.is_active is False
        assert et.available_skills == ["skill-a"]
        assert service.db.commit.called
        assert service.db.refresh.called


class TestGetAndList:
    def test_get_requires_identifier(self, service):
        with pytest.raises(ValueError, match="entity_type_id or slug"):
            service.get_entity_type("t1")

    def test_get_by_slug_not_found(self, service):
        _chain(service.db, first_result=None)
        result = service.get_entity_type("t1", slug="nope")
        assert result is None

    def test_get_by_slug_include_inactive(self, service):
        _chain(service.db, first_result=_etype(is_active=False))
        result = service.get_entity_type("t1", slug="customer", include_inactive=True)
        assert result.slug == "customer"
        filter_args = service.db.query.return_value.filter.call_args_list
        assert not any("is_active" in str(a) for a in filter_args)

    def test_get_by_id(self, service):
        _chain(service.db, first_result=_etype())
        result = service.get_entity_type("t1", entity_type_id="et-1")
        assert result.id == "et-1"

    def test_list_all_statuses_includes_system(self, service):
        rows = [_etype(id="s1", is_system=True), _etype(id="s2")]
        q = _chain(service.db, all_result=rows)
        result = service.list_entity_types("t1", include_system=True, is_active=None)
        assert len(result) == 2
        calls = [str(a) for a in q.filter.call_args_list]
        assert not any("is_active" in c for c in calls)
        assert not any("is_system" in c for c in calls)

    def test_list_search_pattern(self, service):
        rows = [_etype()]
        q = _chain(service.db, all_result=rows)
        service.list_entity_types("t1", search="cust")
        # tenant + is_active + system-exclusion filters, then or_(...) search
        assert len(q.filter.call_args_list) == 4

    def test_list_defaults(self, service):
        rows = [_etype()]
        q = _chain(service.db, all_result=rows)
        service.list_entity_types("t1")
        assert q.order_by.called
        assert q.limit.called
        assert q.offset.called


class TestUpdate:
    def test_update_not_found(self, service):
        _chain(service.db, first_result=None)
        with pytest.raises(ValueError, match="not found"):
            service.update_entity_type("t1", "missing")

    def test_update_system_blocked(self, service):
        _chain(service.db, first_result=_etype(is_system=True))
        with pytest.raises(ValueError, match="read-only"):
            service.update_entity_type("t1", "et-1", display_name="X")

    def test_update_with_schema_invalidates_and_bumps(self, service):
        et = _etype(version=3, available_skills=None, json_schema={"type": "object"})
        _chain(service.db, first_result=et)
        result = service.update_entity_type(
            "t1", "et-1",
            json_schema={"type": "object", "properties": {"x": {"type": "number"}}},
            changed_by="alice",
            change_summary="add x",
        )
        assert result.version == 4
        service.model_factory.invalidate_cache.assert_called_once_with("t1", "customer")
        assert service.db.add.called  # version snapshot
        assert service.db.commit.called

    def test_update_no_fields_no_snapshot(self, service):
        et = _etype(available_skills=["a"], description="old")
        _chain(service.db, first_result=et)
        result = service.update_entity_type("t1", "et-1")
        assert not service.db.add.called  # no snapshot when nothing changed
        assert result.version == 1

    def test_update_display_name_snapshot_and_fields(self, service):
        et = _etype(available_skills=["a"], description="old")
        _chain(service.db, first_result=et)
        result = service.update_entity_type(
            "t1", "et-1", display_name="New Name", description="new", available_skills=["b"]
        )
        assert result.display_name == "New Name"
        assert result.description == "new"
        assert result.available_skills == ["b"]
        assert service.db.add.called  # snapshot created for field change
        assert result.version == 1

    def test_update_invalid_new_schema(self, service):
        et = _etype()
        _chain(service.db, first_result=et)
        service.validator.validate_schema.return_value = (False, "broken")
        with pytest.raises(ValueError, match="Invalid JSON Schema"):
            service.update_entity_type("t1", "et-1", json_schema={"broken": 1})

    def test_update_commit_error(self, service):
        et = _etype()
        _chain(service.db, first_result=et)
        service.db.commit.side_effect = RuntimeError("boom")
        with pytest.raises(RuntimeError):
            service.update_entity_type("t1", "et-1", display_name="X")
        assert service.db.rollback.called


class TestDelete:
    def test_delete_not_found(self, service):
        _chain(service.db, first_result=None)
        assert service.delete_entity_type("t1", "missing") is False

    def test_delete_system_blocked(self, service):
        _chain(service.db, first_result=_etype(is_system=True))
        with pytest.raises(ValueError, match="read-only"):
            service.delete_entity_type("t1", "et-1")

    def test_delete_soft(self, service):
        et = _etype(is_active=True)
        _chain(service.db, first_result=et)
        result = service.delete_entity_type("t1", "et-1")
        assert result is True
        assert et.is_active is False
        assert not service.db.delete.called
        service.model_factory.invalidate_cache.assert_called_once()

    def test_delete_hard(self, service):
        et = _etype()
        _chain(service.db, first_result=et)
        result = service.delete_entity_type("t1", "et-1", hard_delete=True)
        assert result is True
        service.db.delete.assert_called_once_with(et)
        assert service.db.commit.called

    def test_delete_soft_commit_error(self, service):
        et = _etype()
        _chain(service.db, first_result=et)
        service.db.commit.side_effect = RuntimeError("boom")
        with pytest.raises(RuntimeError):
            service.delete_entity_type("t1", "et-1")
        assert service.db.rollback.called

    def test_delete_hard_commit_error(self, service):
        et = _etype()
        _chain(service.db, first_result=et)
        service.db.commit.side_effect = RuntimeError("boom")
        with pytest.raises(RuntimeError):
            service.delete_entity_type("t1", "et-1", hard_delete=True)
        assert service.db.rollback.called


class TestCountAndCompare:
    def test_count_excludes_system_by_default(self, service):
        q = _chain(service.db)
        q.count.return_value = 3
        count = service.count_entity_types("t1")
        assert count == 3
        # tenant+active filter, then the is_system exclusion filter
        assert len(q.filter.call_args_list) == 2

    def test_count_includes_system(self, service):
        q = _chain(service.db)
        q.count.return_value = 5
        count = service.count_entity_types("t1", include_system=True)
        assert count == 5
        calls = [str(a) for a in q.filter.call_args_list]
        assert not any("is_system" in c for c in calls)

    def _snapshots(self, service, from_schema, to_schema):
        q = Mock()
        q.filter = Mock(return_value=q)
        q.first = Mock(
            side_effect=[
                SimpleNamespace(json_schema=from_schema),
                SimpleNamespace(json_schema=to_schema),
            ]
        )
        service.db.query = Mock(return_value=q)

    def test_compare_add_remove_replace(self, service):
        self._snapshots(
            service,
            {"properties": {"a": {"type": "string"}, "b": {"type": "number"}}, "required": ["a"]},
            {"properties": {"a": {"type": "integer"}, "c": {"type": "boolean"}}, "required": ["a", "c"]},
        )
        _, _, ops = service.compare_schema_versions("t1", "et-1", 1, 2)
        paths = [(o["op"], o["path"]) for o in ops]
        assert ("add", "/properties/c") in paths
        assert ("remove", "/properties/b") in paths
        assert ("replace", "/properties/a") in paths
        assert ("add", "/required/-") in paths

    def test_compare_required_removal_ops(self, service):
        self._snapshots(
            service,
            {"properties": {"a": {"type": "string"}}, "required": ["a", "b"]},
            {"properties": {"a": {"type": "string"}}, "required": ["a"]},
        )
        _, _, ops = service.compare_schema_versions("t1", "et-1", 1, 2)
        assert ("remove", "/required/b") in [(o["op"], o["path"]) for o in ops]

    def test_compare_unchanged_schema(self, service):
        schema = {"properties": {"a": {"type": "string"}}, "required": ["a"]}
        self._snapshots(service, schema, dict(schema))
        _, _, ops = service.compare_schema_versions("t1", "et-1", 1, 2)
        assert ops == []


class TestClose:
    def test_close_unowned_session_not_closed(self):
        db = Mock(spec=Session)
        svc = EntityTypeService(db=db)
        svc.close()
        db.close.assert_not_called()
