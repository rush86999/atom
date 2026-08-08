"""
Bug-hunt + coverage tests for core.entity_type_service (round 2).

These tests target UNcovered code paths and verify REAL bugs found via TDD.
Each bug test is prefixed ``BUG:`` and was written BEFORE the source fix,
confirmed to fail for the right reason, then verified to pass after the fix.
"""
import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy.orm import Session
from typing import Dict, Any

from core.entity_type_service import EntityTypeService
from core.models import EntityTypeDefinition


# ---------------------------------------------------------------------------
# Fixtures (mirror the unit-test mocking style so we don't need Postgres)
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_db():
    return Mock(spec=Session)


@pytest.fixture
def service(mock_db):
    with patch("core.entity_type_service.get_schema_validator"), \
         patch("core.entity_type_service.get_model_factory"):
        svc = EntityTypeService(db=mock_db)
        svc.validator = Mock()
        svc.model_factory = Mock()
        return svc


@pytest.fixture
def valid_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "amount": {"type": "number"},
        },
        "required": ["name"],
    }


# ============================================================================
# BUG #1: _generate_json_patch emits wrong / missing "required" operations
# ============================================================================
class TestGenerateJsonPatchRequiredBug:
    """BUG: _generate_json_patch mishandles `required` field changes.

    The loop at the bottom of ``_generate_json_patch`` had a tautological
    condition (``prop not in added_required`` while iterating ``added_required``)
    AND-ed with ``prop in from_props``. Net effect:
      * newly-added properties that are ALSO newly-required never got a
        ``/required/-`` add op (they were skipped), and
      * the property-additions block above emitted a *bogus*
        ``/required/<prop>`` op (invalid JSON Patch path) for those same fields.

    So a schema evolution that adds a new required field produced an invalid
    patch (wrong path) AND omitted the correct append op.
    """

    def test_bug_new_property_marked_required_emits_valid_required_add(self, service):
        """BUG: adding a new required property must emit a /required/- append op."""
        from_schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
        to_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"},
            },
            "required": ["name", "email"],  # email is new AND newly-required
        }

        ops = service._generate_json_patch(from_schema, to_schema)

        required_adds = [
            o for o in ops
            if o.get("op") == "add" and o.get("path", "").startswith("/required")
        ]
        # There must be exactly ONE required add for "email", using the valid
        # JSON Patch append path "/required/-".
        assert len(required_adds) == 1, f"expected 1 required add, got {required_adds}"
        assert required_adds[0]["path"] == "/required/-"
        assert required_adds[0]["value"] == "email"

    def test_bug_no_bogus_required_path_for_newly_required_property(self, service):
        """BUG: must not emit invalid ``/required/<name>`` path (value must be
        the field name string for an append, not ``True``)."""
        from_schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
        to_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"},
            },
            "required": ["name", "email"],
        }

        ops = service._generate_json_patch(from_schema, to_schema)

        bogus = [
            o for o in ops
            if o.get("path") == "/required/email"  # invalid: not a valid index
        ]
        assert bogus == [], f"invalid /required/<name> op emitted: {bogus}"

    def test_existing_property_becoming_required_emits_append(self, service):
        """An EXISTING property that becomes required must also emit /required/-."""
        from_schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}, "email": {"type": "string"}},
            "required": ["name"],
        }
        to_schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}, "email": {"type": "string"}},
            "required": ["name", "email"],
        }

        ops = service._generate_json_patch(from_schema, to_schema)
        required_adds = [o for o in ops if o.get("path") == "/required/-"]
        assert len(required_adds) == 1
        assert required_adds[0]["value"] == "email"

    def test_removed_required_field_emits_remove_op(self, service):
        """Removing a required field (but keeping the property) emits remove op."""
        from_schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}, "email": {"type": "string"}},
            "required": ["name", "email"],
        }
        to_schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}, "email": {"type": "string"}},
            "required": ["name"],
        }

        ops = service._generate_json_patch(from_schema, to_schema)
        removes = [o for o in ops if o.get("op") == "remove" and "required" in o.get("path", "")]
        assert len(removes) == 1
        assert removes[0]["value"] == "email"


# ============================================================================
# Coverage for compare_schema_versions (uncovered path -> _generate_json_patch)
# ============================================================================
class TestCompareSchemaVersions:
    def _setup_snapshots(self, mock_db, from_schema, to_schema):
        from_snap = Mock()
        from_snap.json_schema = from_schema
        to_snap = Mock()
        to_snap.json_schema = to_schema

        def query_filter(*args, **kwargs):
            m = Mock()
            # chain .filter().first()
            m.filter.return_value = m
            m.first.side_effect = [from_snap, to_snap]
            return m

        mock_db.query.return_value.filter.return_value = m if False else Mock()
        # Simpler: configure sequential .first() calls
        chain = Mock()
        chain.filter.return_value = chain
        chain.first.side_effect = [from_snap, to_snap]
        mock_db.query.return_value.filter.return_value = chain

    def test_compare_returns_schemas_and_patch(self, service, mock_db):
        from_schema = {
            "type": "object",
            "properties": {"a": {"type": "string"}},
            "required": ["a"],
        }
        to_schema = {
            "type": "object",
            "properties": {"a": {"type": "string"}, "b": {"type": "number"}},
            "required": ["a", "b"],
        }
        self._setup_snapshots(mock_db, from_schema, to_schema)

        from_s, to_s, patch = service.compare_schema_versions(
            "t1", "et1", from_version=1, to_version=2
        )
        assert from_s == from_schema
        assert to_s == to_schema
        assert any(o.get("path") == "/properties/b" for o in patch)
        assert any(o.get("path") == "/required/-" and o.get("value") == "b" for o in patch)

    def test_compare_raises_when_version_missing(self, service, mock_db):
        chain = Mock()
        chain.filter.return_value = chain
        chain.first.return_value = None  # version not found
        mock_db.query.return_value.filter.return_value = chain

        with pytest.raises(ValueError, match="Version not found"):
            service.compare_schema_versions("t1", "et1", 1, 99)


# ============================================================================
# Coverage: detect_breaking_changes (uncovered)
# ============================================================================
class TestDetectBreakingChanges:
    def test_detects_required_property_removal_as_critical(self, service):
        et = Mock(spec=EntityTypeDefinition)
        et.json_schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}, "email": {"type": "string"}},
            "required": ["name", "email"],
        }
        service.get_entity_type = Mock(return_value=et)

        new_schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},  # email removed
            "required": ["name"],
        }
        report = service.detect_breaking_changes("t1", "et1", new_schema)

        assert report["has_breaking_changes"] is True
        assert report["summary"]["critical"] == 1
        removed = [c for c in report["changes"] if c["type"] == "property_removed"]
        assert len(removed) == 1
        assert removed[0]["property"] == "email"
        assert removed[0]["severity"] == "critical"

    def test_detects_required_addition_as_warning(self, service):
        et = Mock(spec=EntityTypeDefinition)
        et.json_schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": [],
        }
        service.get_entity_type = Mock(return_value=et)

        new_schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],  # name now required
        }
        report = service.detect_breaking_changes("t1", "et1", new_schema)
        assert report["summary"]["warning"] >= 1
        assert report["has_breaking_changes"] is True

    def test_detects_type_change_as_warning(self, service):
        et = Mock(spec=EntityTypeDefinition)
        et.json_schema = {
            "type": "object",
            "properties": {"age": {"type": "string"}},
        }
        service.get_entity_type = Mock(return_value=et)

        new_schema = {
            "type": "object",
            "properties": {"age": {"type": "number"}},
        }
        report = service.detect_breaking_changes("t1", "et1", new_schema)
        type_changes = [c for c in report["changes"] if c["type"] == "property_type_changed"]
        assert len(type_changes) == 1
        assert type_changes[0]["details"] == {"from": "string", "to": "number"}

    def test_raises_when_entity_type_missing(self, service):
        service.get_entity_type = Mock(return_value=None)
        with pytest.raises(ValueError, match="not found"):
            service.detect_breaking_changes("t1", "et1", {})


# ============================================================================
# Coverage: rollback_to_version (uncovered)
# ============================================================================
class TestRollbackToVersion:
    def test_rollback_restores_schema_and_increments_version(self, service, mock_db):
        et = Mock(spec=EntityTypeDefinition)
        et.is_system = False
        et.version = 5
        et.slug = "invoice"
        et.tenant_id = "t1"
        et.id = "et1"
        et.json_schema = {"type": "object", "properties": {"new": {"type": "string"}}}
        et.display_name = "Current"
        et.description = "current desc"
        et.available_skills = ["s2"]
        service.get_entity_type = Mock(return_value=et)

        target = Mock()
        target.json_schema = {"type": "object", "properties": {"old": {"type": "string"}}}
        target.display_name = "Old Invoice"
        target.description = "v2 desc"
        target.available_skills = ["s1"]

        chain = Mock()
        chain.filter.return_value = chain
        chain.first.return_value = target
        mock_db.query.return_value.filter.return_value = chain

        result = service.rollback_to_version("t1", "et1", target_version=2)
        assert result is et
        assert et.version == 6  # incremented
        assert et.json_schema == {"type": "object", "properties": {"old": {"type": "string"}}}
        assert et.display_name == "Old Invoice"
        service.model_factory.invalidate_cache.assert_called_once_with("t1", "invoice")

    def test_rollback_rejects_system_type(self, service):
        et = Mock(spec=EntityTypeDefinition)
        et.is_system = True
        et.slug = "system_thing"
        service.get_entity_type = Mock(return_value=et)
        with pytest.raises(ValueError, match="Cannot rollback system"):
            service.rollback_to_version("t1", "et1", target_version=1)

    def test_rollback_rejects_target_ge_current(self, service, mock_db):
        et = Mock(spec=EntityTypeDefinition)
        et.is_system = False
        et.version = 3
        et.slug = "x"
        service.get_entity_type = Mock(return_value=et)

        target = Mock()
        chain = Mock()
        chain.filter.return_value = chain
        chain.first.return_value = target
        mock_db.query.return_value.filter.return_value = chain

        with pytest.raises(ValueError, match="Cannot rollback to version"):
            service.rollback_to_version("t1", "et1", target_version=3)

    def test_rollback_raises_when_target_missing(self, service, mock_db):
        et = Mock(spec=EntityTypeDefinition)
        et.is_system = False
        et.version = 3
        et.slug = "x"
        service.get_entity_type = Mock(return_value=et)

        chain = Mock()
        chain.filter.return_value = chain
        chain.first.return_value = None
        chain.all.return_value = []
        mock_db.query.return_value.filter.return_value = chain

        with pytest.raises(ValueError, match="Version 1 not found"):
            service.rollback_to_version("t1", "et1", target_version=1)


# ============================================================================
# Coverage: count_entity_types + list search + slug validation
# ============================================================================
class TestCountAndMisc:
    def test_count_entity_types_excludes_system_by_default(self, service, mock_db):
        chain = Mock()
        chain.filter.return_value = chain
        chain.count.return_value = 7
        mock_db.query.return_value.filter.return_value = chain

        assert service.count_entity_types("t1") == 7

    def test_count_includes_system_when_requested(self, service, mock_db):
        chain = Mock()
        chain.filter.return_value = chain
        chain.count.return_value = 2
        mock_db.query.return_value.filter.return_value = chain
        assert service.count_entity_types("t1", include_system=True) == 2

    def test_is_valid_slug_accepts_valid(self, service):
        assert service._is_valid_slug("invoice-123_abc") is True

    def test_is_valid_slug_rejects_invalid(self, service):
        assert service._is_valid_slug("invoice 123") is False  # space
        assert service._is_valid_slug("invéoice") is False     # non-ascii
        assert service._is_valid_slug("") is False             # empty

    def test_is_valid_slug_rejects_overlong(self, service):
        assert service._is_valid_slug("a" * 101) is False

    def test_normalize_type_handles_enum_and_ref(self, service):
        assert service._normalize_type({"type": "string"}) == "string"
        assert service._normalize_type({"type": ["string", "null"]}) == "string | null"
        assert service._normalize_type({"$ref": "#/defs/X"}) == "#/defs/X"
        assert service._normalize_type({"enum": ["a", "b"]}) == "enum: [a, b]"
        assert service._normalize_type({}) == "unknown"


# ============================================================================
# Coverage: merge_entity_types (mostly uncovered)
# ============================================================================
class TestMergeEntityTypes:
    def test_merge_migrates_nodes_and_deactivates_source(self, service, mock_db):
        source = Mock(spec=EntityTypeDefinition)
        source.slug = "draft_inv"
        source.metadata_json = {"discovery_reasoning": "auto"}
        source.is_active = True
        source.description = ""

        target = Mock(spec=EntityTypeDefinition)
        target.metadata_json = None

        # get_entity_type called twice: source (include_inactive=True), target (by slug)
        service.get_entity_type = Mock(side_effect=[source, target])

        # GraphNode update query
        update_chain = Mock()
        update_chain.filter.return_value = update_chain
        update_chain.update.return_value = 5  # nodes updated
        mock_db.query.return_value.filter.return_value = update_chain

        result = service.merge_entity_types("t1", "src-1", "invoice", workspace_id="ws1")
        assert result is True
        assert source.is_active is False
        assert "Merged into invoice" in source.description
        assert target.metadata_json["merges"][0]["source_slug"] == "draft_inv"
        assert target.metadata_json["merges"][0]["nodes_count"] == 5

    def test_merge_raises_when_source_missing(self, service):
        service.get_entity_type = Mock(return_value=None)
        with pytest.raises(ValueError, match="Source entity type"):
            service.merge_entity_types("t1", "missing", "invoice")
