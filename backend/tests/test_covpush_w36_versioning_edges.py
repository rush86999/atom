"""Coverage wave 36 — core/workflow_versioning_system.py edge branches (TDD).

Picks up where the existing versioning suites left off (94%, 470/498). The
remaining 28 lines are all "no row found" early-return branches and the
exception paths of the read methods:
- get_version / get_latest_version / get_version_history / get_branches /
  get_version_metrics / update_version_metrics (missing row + exception)
- _bump_version invalid version_type + boundary rollover
- _calculate_version_diff step-change fallthrough branches
- merge_branch conflict-resolution edge
- WorkflowVersionManager.create_workflow_version exception paths
"""
import asyncio
import json
import os
import tempfile
from unittest.mock import patch

import pytest

from core.workflow_versioning_system import (
    VersionType,
    WorkflowVersioningSystem,
    WorkflowVersionManager,
)


def _system(tmpdir, name="versions.db"):
    return WorkflowVersioningSystem(db_path=f"{tmpdir}/{name}")


async def _seed(system, workflow_id="wf-1", n=2, created_by="u-1"):
    for i in range(n):
        await system.create_version(
            workflow_id=workflow_id,
            workflow_data={"name": f"v{i}", "steps": [{"id": f"s{i}"}]},
            version_type=VersionType.MINOR,
            created_by=created_by,
            commit_message=f"commit {i}",
        )


class TestVersioningEdges:
    async def test_get_version_not_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            system = _system(tmp)
            assert await system.get_version("wf-x", "v1") is None

    async def test_get_version_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            system = _system(tmp)
            with patch("core.workflow_versioning_system.sqlite3.connect",
                       side_effect=RuntimeError("db down")):
                assert await system.get_version("wf-x", "v1") is None

    async def test_get_latest_version_not_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            system = _system(tmp)
            assert await system.get_latest_version("wf-x", "main") is None

    async def test_get_latest_version_no_branch_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            system = _system(tmp)
            await _seed(system, "wf-1")
            # workflow exists but no versions on this branch
            assert await system.get_latest_version("wf-1", "feature-x") is None

    async def test_get_latest_version_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            system = _system(tmp)
            with patch("core.workflow_versioning_system.sqlite3.connect",
                       side_effect=RuntimeError("db down")):
                assert await system.get_latest_version("wf-x") is None

    async def test_get_version_history_not_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            system = _system(tmp)
            assert await system.get_version_history("wf-x") == []

    async def test_get_version_history_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            system = _system(tmp)
            with patch("core.workflow_versioning_system.sqlite3.connect",
                       side_effect=RuntimeError("db down")):
                assert await system.get_version_history("wf-x") == []

    async def test_get_branches_not_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            system = _system(tmp)
            assert await system.get_branches("wf-x") == []

    async def test_get_branches_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            system = _system(tmp)
            with patch("core.workflow_versioning_system.sqlite3.connect",
                       side_effect=RuntimeError("db down")):
                assert await system.get_branches("wf-x") == []

    async def test_get_version_metrics_not_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            system = _system(tmp)
            assert await system.get_version_metrics("wf-x", "v1") is None

    async def test_get_version_metrics_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            system = _system(tmp)
            with patch("core.workflow_versioning_system.sqlite3.connect",
                       side_effect=RuntimeError("db down")):
                assert await system.get_version_metrics("wf-x", "v1") is None

    async def test_update_version_metrics_inserts_missing_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            system = _system(tmp)
            await _seed(system, "wf-m")
            # Missing version row → upsert creates it (returns True)
            ok = await system.update_version_metrics(
                "wf-m", "v99",
                {"success": True, "execution_time": 100.0})
            assert ok is True
            metrics = await system.get_version_metrics("wf-m", "v99")
            assert metrics is not None
            assert metrics["execution_count"] == 1

    async def test_update_version_metrics_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            system = _system(tmp)
            with patch("core.workflow_versioning_system.sqlite3.connect",
                       side_effect=RuntimeError("db down")):
                assert await system.update_version_metrics(
                    "wf-x", "v1", {"execution_result": "success"}) is False

    def test_bump_version_invalid_type_falls_through(self):
        with tempfile.TemporaryDirectory() as tmp:
            system = _system(tmp)
            # Unknown type falls through without bumping any component
            assert system._bump_version("1.2.3", "not-a-version-type") == "1.2.3"  # type: ignore

    def test_bump_version_patch_rollover(self):
        with tempfile.TemporaryDirectory() as tmp:
            system = _system(tmp)
            assert system._bump_version("1.0.9", VersionType.PATCH) == "1.0.10"
            assert system._bump_version("1.9.9", VersionType.MINOR) == "1.10.0"
            assert system._bump_version("9.9.9", VersionType.MAJOR) == "10.0.0"

    def test_bump_version_prerelease_branches(self):
        from core.workflow_versioning_system import VersionType as VT
        with tempfile.TemporaryDirectory() as tmp:
            system = _system(tmp)
            # BETA on existing prerelease: beta.2 → beta.3
            assert system._bump_version("1.0.0-beta.2", VT.BETA) == "1.0.0-beta.3"
            # BETA on plain version: adds beta.1
            assert system._bump_version("1.0.0", VT.BETA) == "1.0.0-beta.1"
            # ALPHA on existing prerelease
            assert system._bump_version("1.0.0-alpha.2", VT.ALPHA) == "1.0.0-alpha.3"
            # ALPHA on plain version
            assert system._bump_version("1.0.0", VT.ALPHA) == "1.0.0-alpha.1"

    def test_bump_version_exception_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            system = _system(tmp)
            # Non-numeric parts raise inside the try → fallback appends .1
            assert system._bump_version("abc.def.ghi", VersionType.MAJOR) == "abc.def.ghi.1"

    async def test_merge_branch_conflict_resolution(self):
        with tempfile.TemporaryDirectory() as tmp:
            system = _system(tmp)
            await _seed(system, "wf-mb", n=1)
            latest = await system.get_latest_version("wf-mb")
            await system.create_branch("wf-mb", "feature-x", latest.version, "u-1")
            await system.create_version(
                workflow_id="wf-mb", workflow_data={"x": 2},
                version_type=VersionType.MINOR,
                created_by="u-1", commit_message="feature work",
                branch_name="feature-x")
            result = await system.merge_branch(
                "wf-mb", "feature-x", "main",
                merge_by="u-1", merge_message="merge it")
            assert result is not None
            assert result.workflow_id == "wf-mb"

    async def test_version_manager_create_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            system = _system(tmp)
            manager = WorkflowVersionManager()
            manager.versioning_system = system
            with patch.object(system, "create_version",
                              side_effect=RuntimeError("boom")):
                with pytest.raises(RuntimeError, match="boom"):
                    await manager.create_workflow_version(
                        workflow_id="wf-vm", workflow_data={"x": 1},
                        user_id="u-1", change_description="m")

    async def test_version_manager_rollback_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            system = _system(tmp)
            manager = WorkflowVersionManager()
            manager.versioning_system = system
            with patch.object(system, "rollback_to_version",
                              side_effect=RuntimeError("boom")):
                with pytest.raises(RuntimeError, match="boom"):
                    await manager.rollback_workflow("wf-vm", "v1", "u-1", "reason")

    async def test_merge_branch_missing_source_version(self):
        """Branch row's current_version pointing at a deleted version row →
        ValueError. (Branch current_version starts at base_version which lives
        on main, so the row normally exists — the guard is defensive.)"""
        with tempfile.TemporaryDirectory() as tmp:
            system = _system(tmp)
            await _seed(system, "wf-mv", n=1)
            latest = await system.get_latest_version("wf-mv")
            await system.create_branch("wf-mv", "orphan", latest.version, "u-1")
            # Force the branch's current_version to a version that doesn't exist
            conn = __import__("sqlite3").connect(f"{tmp}/versions.db")
            conn.execute("UPDATE workflow_branches SET current_version = '9.9.9' "
                         "WHERE branch_name = 'orphan'")
            conn.commit()
            conn.close()
            with pytest.raises(ValueError, match="Source version .* not found"):
                await system.merge_branch(
                    "wf-mv", "orphan", "main", merge_by="u-1", merge_message="x")

    async def test_version_manager_auto_detect(self):
        with tempfile.TemporaryDirectory() as tmp:
            system = _system(tmp)
            manager = WorkflowVersionManager()
            manager.versioning_system = system
            await _seed(system, "wf-auto", n=1)
            result = await manager.create_workflow_version(
                workflow_id="wf-auto", workflow_data={"new": "field"},
                user_id="u-1", change_description="auto bump", version_type="auto")
            assert result["version"] is not None
            assert result["change_type"] is not None

    async def test_version_manager_patch_hotfix_types(self):
        with tempfile.TemporaryDirectory() as tmp:
            system = _system(tmp)
            manager = WorkflowVersionManager()
            manager.versioning_system = system
            await _seed(system, "wf-pt", n=1)
            for vtype in ("patch", "hotfix", "major"):
                result = await manager.create_workflow_version(
                    workflow_id="wf-pt", workflow_data={"step": vtype},
                    user_id="u-1", change_description=vtype, version_type=vtype)
                assert result["version"] is not None

    async def test_version_manager_unknown_type_defaults_minor(self):
        with tempfile.TemporaryDirectory() as tmp:
            system = _system(tmp)
            manager = WorkflowVersionManager()
            manager.versioning_system = system
            await _seed(system, "wf-unk", n=1)
            result = await manager.create_workflow_version(
                workflow_id="wf-unk", workflow_data={"step": "x"},
                user_id="u-1", change_description="x", version_type="bogus")
            assert result["version_type"] == "minor"

    async def test_compare_versions_step_count_and_deps(self):
        """_calculate_version_diff structural + dependency branches."""
        with tempfile.TemporaryDirectory() as tmp:
            system = _system(tmp)
            v1 = await system.create_version(
                workflow_id="wf-diff",
                workflow_data={"steps": [{"id": "a", "type": "action"},
                                         {"id": "b", "type": "action"}],
                               "dependencies": ["a"], "name": "n1"},
                version_type=VersionType.MAJOR, created_by="u-1",
                commit_message="init")
            v2 = await system.create_version(
                workflow_id="wf-diff",
                workflow_data={"steps": [{"id": "a", "type": "condition"},  # structural type change
                                         {"id": "b", "type": "action"}],
                               "dependencies": ["a", "b"],  # deps changed
                               "name": "n2"},  # metadata changed
                version_type=VersionType.MAJOR, created_by="u-1",
                commit_message="v2")
            diff = await system.compare_versions(
                "wf-diff", v1.version, v2.version)
            assert diff is not None
            assert diff.structural_changes or diff.dependency_changes or diff.metadata_changes

    async def test_version_manager_auto_detect_execution_change(self):
        """auto-detect maps EXECUTION change → MINOR bump (line 1266)."""
        with tempfile.TemporaryDirectory() as tmp:
            system = _system(tmp)
            manager = WorkflowVersionManager()
            manager.versioning_system = system
            await _seed(system, "wf-auto2", n=1)
            result = await manager.create_workflow_version(
                workflow_id="wf-auto2",
                workflow_data={"steps": [{"id": "s0",
                                          "execution_logic": {"timeout": 5}}]},
                user_id="u-1", change_description="execution tweak",
                version_type="auto")
            assert result["version_type"] == "minor"
