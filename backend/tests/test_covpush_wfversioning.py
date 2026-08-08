"""Coverage-push + bug-hunt tests for core.orchestration.workflow_versioning.

Bugs found via red tests first:
- V2: ``list_versions`` crashes (ValueError) on non-semantic version strings
  even though ``versioning_scheme`` supports sequential/date-based versions.
- V3: ``increment_version`` crashes (IndexError) on short version strings.
- V4: ``check_compatibility`` returns UNKNOWN for same-major versions where
  ``WorkflowVersion.is_compatible_with`` says COMPATIBLE — manager and
  version-level checks disagree on the same pair.
- V5: ``execute_migration`` completes without advancing the workflow's
  ``current_version`` — a "successful" migration leaves the workflow pinned
  to the old version.
- V6: ``add_version`` silently overwrites an existing version snapshot
  (data loss of changelog/breaking_changes) and appends a duplicate to the
  version history.
- V7: ``_build_migration_steps`` crashes on ``input_schema=None``.
"""

import asyncio
import os

os.environ["TESTING"] = "1"

import pytest
from unittest.mock import AsyncMock

from core.orchestration.workflow_versioning import (
    CompatibilityStatus,
    MigrationPlan,
    MigrationStrategy,
    VersionIncrement,
    VersionSchema,
    VersionedWorkflow,
    VersioningConfig,
    WorkflowVersion,
    WorkflowVersioning,
    get_workflow_versioning,
)


@pytest.fixture(autouse=True)
def _reset_singleton():
    import core.orchestration.workflow_versioning as wv

    wv._versioning_instance = None
    yield
    wv._versioning_instance = None


def _wf(with_schemas=True):
    m = WorkflowVersioning()
    m.create_workflow("wf-1", "Sales Flow", "desc", creator="alice")
    if with_schemas:
        m.add_version(
            "wf-1",
            "1.1.0",
            input_schema={
                "properties": {"name": {"type": "string"}, "email": {"type": "string"}}
            },
            output_schema={"properties": {"result": {"type": "string"}}},
            step_schema={"step1": {"action": "send"}, "step2": {"action": "log"}},
            changelog=["added email"],
            breaking_changes=["output format changed"],
            created_by="bob",
        )
    return m


class TestEnumsAndConfig:
    def test_version_increment_values(self):
        assert VersionIncrement.MAJOR.value == "major"
        assert VersionIncrement.MINOR.value == "minor"
        assert VersionIncrement.PATCH.value == "patch"

    def test_migration_strategy_values(self):
        assert MigrationStrategy.AUTOMATIC.value == "automatic"
        assert MigrationStrategy.MANUAL.value == "manual"
        assert MigrationStrategy.HYBRID.value == "hybrid"
        assert MigrationStrategy.ROLLBACK.value == "rollback"

    def test_compatibility_status_values(self):
        assert CompatibilityStatus.COMPATIBLE.value == "compatible"
        assert CompatibilityStatus.INCOMPATIBLE.value == "incompatible"
        assert CompatibilityStatus.UNKNOWN.value == "unknown"

    def test_versioning_config_defaults(self):
        cfg = VersioningConfig()
        assert cfg.auto_increment is True
        assert cfg.versioning_scheme == "semantic"
        assert cfg.max_versions_per_workflow == 10
        assert cfg.archive_deleted_versions is True
        assert cfg.default_migration_strategy == MigrationStrategy.HYBRID
        assert cfg.migration_timeout_seconds == 300
        assert cfg.validate_on_migration is True
        assert cfg.rollback_on_validation_failure is True

    def test_dataclass_defaults(self):
        v = WorkflowVersion()
        assert v.version == "1.0.0"
        assert v.is_latest is True
        assert v.deprecated is False
        schema = VersionSchema()
        assert schema.version == "1.0.0"
        assert schema.step_schemas == {}
        plan = MigrationPlan()
        assert plan.status == "pending"
        assert plan.strategy == MigrationStrategy.HYBRID
        wf = VersionedWorkflow()
        assert wf.current_version == "1.0.0"
        assert wf.versions == {}


class TestWorkflowVersionCompat:
    def test_is_compatible_explicit_list(self):
        v = WorkflowVersion(version="2.0.0", compatible_with=["1.0.0"])
        assert v.is_compatible_with("1.0.0") is True

    def test_is_incompatible_explicit_list(self):
        v = WorkflowVersion(version="2.0.0", incompatible_with=["1.0.0"])
        assert v.is_compatible_with("1.0.0") is False

    def test_is_compatible_same_major(self):
        v = WorkflowVersion(version="1.5.0")
        assert v.is_compatible_with("1.2.0") is True

    def test_is_compatible_diff_major(self):
        v = WorkflowVersion(version="2.0.0")
        assert v.is_compatible_with("1.9.0") is False

    def test_is_compatible_unparseable_fail_open(self):
        v = WorkflowVersion(version="2.0.0")
        assert v.is_compatible_with("alpha") is True

    def test_get_major_minor(self):
        v = WorkflowVersion(version="3.7.1")
        assert v.get_major_minor() == (3, 7)

    def test_get_major_minor_bad_version(self):
        v = WorkflowVersion(version="nonsense")
        assert v.get_major_minor() == (1, 0)


class TestCreateAndAddVersion:
    def test_create_workflow(self):
        m = WorkflowVersioning()
        wf = m.create_workflow("wf-1", "name", "desc", version="1.0.0", creator="carol")
        assert wf.workflow_id == "wf-1"
        assert wf.current_version == "1.0.0"
        v = m.get_version("wf-1", "1.0.0")
        assert v is not None
        assert v.created_by == "carol"
        assert v.is_latest is True

    def test_add_version_to_missing_workflow_raises(self):
        m = WorkflowVersioning()
        with pytest.raises(ValueError):
            m.add_version("nope", "1.0.0", {}, {}, {})

    def test_add_version_updates_latest_flags(self):
        m = _wf()
        v2 = m.get_version("wf-1", "1.1.0")
        v1 = m.get_version("wf-1", "1.0.0")
        assert v2.is_latest is True
        assert v1.is_latest is False
        assert m.get_latest_version("wf-1").version == "1.1.0"
        schema = m._workflows["wf-1"].schemas["1.1.0"]
        assert schema.schema_id == "schema_wf-1_v_1_1_0"
        assert schema.step_schemas == {"default": {"step1": {"action": "send"}, "step2": {"action": "log"}}}

    def test_version_id_format(self):
        m = WorkflowVersioning()
        m.create_workflow("wf-1", "n", "d")
        v = m.add_version("wf-1", "2.0.0", {}, {}, {})
        assert v.version_id == "wf-1_v_2_0_0"

    def test_duplicate_version_raises(self):
        m = _wf()
        with pytest.raises(ValueError):
            m.add_version("wf-1", "1.0.0", {"properties": {"hacked": {}}}, {}, {})

    def test_get_version_missing(self):
        m = _wf()
        assert m.get_version("missing", "1.0.0") is None
        assert m.get_version("wf-1", "9.9.9") is None
        assert m.get_latest_version("missing") is None

    def test_list_versions_sorted_desc(self):
        m = _wf()
        versions = m.list_versions("wf-1")
        assert [v.version for v in versions] == ["1.1.0", "1.0.0"]
        assert m.list_versions("missing") == []

    def test_list_versions_non_semantic_no_crash(self):
        m = _wf()
        m.add_version("wf-1", "2026-08-01", {}, {}, {}, created_by="bot")
        versions = m.list_versions("wf-1")
        assert len(versions) == 3

    def test_deprecate_version(self):
        m = _wf()
        assert m.deprecate_version("wf-1", "1.0.0") is True
        v = m.get_version("wf-1", "1.0.0")
        assert v.deprecated is True
        assert v.deprecated_at is not None
        assert m.deprecate_version("wf-1", "9.9.9") is False

    def test_statistics(self):
        m = _wf()
        stats = m.get_statistics()
        assert stats["total_workflows"] == 1
        assert stats["total_versions"] == 2
        assert stats["config"]["max_versions"] == 10


class TestMigration:
    def test_create_migration_plan_missing_versions(self):
        m = WorkflowVersioning()
        m.create_workflow("wf-1", "n", "d")
        with pytest.raises(ValueError):
            m.create_migration_plan("wf-1", "1.0.0", "2.0.0")

    def test_create_migration_plan_steps(self):
        m = _wf()
        plan = m.create_migration_plan("wf-1", "1.0.0", "1.1.0")
        assert plan.migration_id == "mig_wf-1_1.0.0_to_1.1.0"
        assert "Address breaking changes: output format changed" in plan.steps
        assert "Update input data to match new schema" in plan.steps
        assert "Update output data consumers for new schema" in plan.steps
        assert "Update step configurations" in plan.steps
        params_step = [s for s in plan.steps if s.startswith("Provide new parameters")][0]
        assert "email" in params_step and "name" in params_step
        assert plan.steps[-1] == "Validate migrated workflow"
        assert m._workflows["wf-1"].migration_plans[("1.0.0", "1.1.0")] is plan

    def test_build_migration_steps_no_changes(self):
        m = WorkflowVersioning()
        m.create_workflow("wf-1", "n", "d")
        m.add_version("wf-1", "1.0.1", {"properties": {"a": {}}}, {"properties": {"b": {}}}, {"s": {}})
        m.add_version("wf-1", "1.0.2", {"properties": {"a": {}}}, {"properties": {"b": {}}}, {"s": {}})
        plan = m.create_migration_plan("wf-1", "1.0.1", "1.0.2")
        assert plan.steps == ["Validate migrated workflow"]

    def test_build_migration_steps_none_schemas(self):
        m = WorkflowVersioning()
        m.create_workflow("wf-1", "n", "d")
        m.add_version("wf-1", "1.0.1", None, None, None)
        m.add_version("wf-1", "1.0.2", None, None, None)
        plan = m.create_migration_plan("wf-1", "1.0.1", "1.0.2")
        assert plan.steps == ["Validate migrated workflow"]

    @pytest.mark.asyncio
    async def test_execute_migration_missing_workflow(self):
        m = WorkflowVersioning()
        assert await m.execute_migration("missing", "mig") is False

    @pytest.mark.asyncio
    async def test_execute_migration_missing_plan(self):
        m = _wf()
        assert await m.execute_migration("wf-1", "nope") is False

    @pytest.mark.asyncio
    async def test_execute_migration_success_advances_current(self):
        m = _wf()
        plan = m.create_migration_plan("wf-1", "1.0.0", "1.1.0")
        ok = await m.execute_migration("wf-1", plan.migration_id)
        assert ok is True
        assert plan.status == "completed"
        assert plan.started_at is not None
        assert plan.completed_at is not None
        assert m._workflows["wf-1"].current_version == "1.1.0"

    @pytest.mark.asyncio
    async def test_execute_migration_failure_rolls_back(self, monkeypatch):
        m = _wf()
        plan = m.create_migration_plan("wf-1", "1.0.0", "1.1.0")
        m._rollback_migration = AsyncMock(return_value=True)
        real_sleep = asyncio.sleep

        async def _boom(*a, **k):
            raise RuntimeError("migration engine down")

        monkeypatch.setattr(asyncio, "sleep", _boom)
        try:
            ok = await m.execute_migration("wf-1", plan.migration_id)
        finally:
            monkeypatch.setattr(asyncio, "sleep", real_sleep)
        assert ok is True
        assert plan.status == "failed"
        assert plan.error is not None
        m._rollback_migration.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_migration_failure_no_rollback(self, monkeypatch):
        m = WorkflowVersioning(
            config=VersioningConfig(rollback_on_validation_failure=False)
        )
        m.create_workflow("wf-1", "n", "d")
        m.add_version("wf-1", "1.1.0", {}, {}, {})
        plan = m.create_migration_plan("wf-1", "1.0.0", "1.1.0")
        real_sleep = asyncio.sleep

        async def _boom(*a, **k):
            raise RuntimeError("migration engine down")

        monkeypatch.setattr(asyncio, "sleep", _boom)
        try:
            ok = await m.execute_migration("wf-1", plan.migration_id)
        finally:
            monkeypatch.setattr(asyncio, "sleep", real_sleep)
        assert ok is False
        assert plan.status == "failed"
        assert "migration engine down" in plan.error

    @pytest.mark.asyncio
    async def test_rollback_migration(self):
        m = WorkflowVersioning()
        assert await m._rollback_migration("wf-1", "mig") is True


class TestCompatibility:
    def test_missing_versions_unknown(self):
        m = WorkflowVersioning()
        assert (
            m.check_compatibility("missing", "1.0.0", "2.0.0")
            == CompatibilityStatus.UNKNOWN
        )

    def test_explicit_incompatible(self):
        m = _wf()
        to_ver = m.get_version("wf-1", "1.1.0")
        to_ver.incompatible_with.append("1.0.0")
        assert (
            m.check_compatibility("wf-1", "1.0.0", "1.1.0")
            == CompatibilityStatus.INCOMPATIBLE
        )

    def test_explicit_compatible(self):
        m = _wf()
        to_ver = m.get_version("wf-1", "1.1.0")
        to_ver.compatible_with.append("1.0.0")
        assert (
            m.check_compatibility("wf-1", "1.0.0", "1.1.0")
            == CompatibilityStatus.COMPATIBLE
        )

    def test_same_major_compatible(self):
        m = _wf()
        assert (
            m.check_compatibility("wf-1", "1.0.0", "1.1.0")
            == CompatibilityStatus.COMPATIBLE
        )

    def test_different_major_incompatible(self):
        m = _wf()
        m.add_version("wf-1", "2.0.0", {}, {}, {})
        assert (
            m.check_compatibility("wf-1", "1.0.0", "2.0.0")
            == CompatibilityStatus.INCOMPATIBLE
        )

    def test_unparseable_versions_unknown(self):
        m = _wf()
        m.add_version("wf-1", "alpha", {}, {}, {})
        assert (
            m.check_compatibility("wf-1", "1.0.0", "alpha")
            == CompatibilityStatus.UNKNOWN
        )


class TestIncrementVersion:
    def test_missing_workflow_raises(self):
        m = WorkflowVersioning()
        with pytest.raises(ValueError):
            m.increment_version("missing")

    def test_major_increment(self):
        m = _wf()
        assert m.increment_version("wf-1", VersionIncrement.MAJOR) == "2.0.0"

    def test_minor_increment(self):
        m = _wf()
        assert m.increment_version("wf-1", VersionIncrement.MINOR) == "1.2.0"

    def test_patch_increment(self):
        m = _wf()
        assert m.increment_version("wf-1", VersionIncrement.PATCH) == "1.1.1"

    def test_default_increment_is_patch(self):
        m = _wf()
        assert m.increment_version("wf-1") == "1.1.1"

    def test_short_version_no_crash(self):
        m = _wf()
        m._workflows["wf-1"].current_version = "1"
        assert m.increment_version("wf-1", VersionIncrement.PATCH) == "1.0.1"


class TestSingleton:
    def test_singleton_creates_once(self):
        cfg = VersioningConfig(max_versions_per_workflow=42)
        instance = get_workflow_versioning(cfg)
        assert instance.config.max_versions_per_workflow == 42
        again = get_workflow_versioning()
        assert again is instance
