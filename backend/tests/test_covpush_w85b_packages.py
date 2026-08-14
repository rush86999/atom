# -*- coding: utf-8 -*-
"""W85B — coverage push: package governance + skill loading/retrieval + supervised queue.

Targets (>=95% statement coverage each, standalone):
  core/npm_package_installer.py        (83% baseline)
  core/package_dependency_scanner.py   (96% baseline)
  core/package_installer.py            (82% baseline)
  core/skill_dynamic_loader.py         (84% baseline)
  core/skill_retrieval_service.py      (87% baseline)
  core/skill_parser.py                 (78% baseline)
  core/supervised_queue_service.py     (64% baseline)

Style: fully mocked deps (docker client, subprocess, sqlalchemy session),
zero network, zero LLM spend, no real DB. Env vars via monkeypatch.
"""
from __future__ import annotations

import asyncio
import importlib
import json
import os
import subprocess
import sys
import tempfile
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import docker
import pytest
from sqlalchemy.orm import Session

from core.models import (
    AgentExecution,
    AgentRegistry,
    QueueStatus,
    SupervisedExecutionQueue,
    User,
    UserActivity,
    UserState,
)
from core.npm_package_installer import NpmPackageInstaller
from core.package_dependency_scanner import PackageDependencyScanner
from core.package_installer import PackageInstaller
from core.skill_dynamic_loader import SkillDynamicLoader, get_global_loader
from core.skill_parser import SkillParser
from core.skill_retrieval_service import SkillRetrievalService, get_skill_retrieval_service
from core.supervised_queue_service import SupervisedQueueService


def _run(coro):
    return asyncio.run(coro)


def _exec_module_as_main(module_name: str):
    """Exec a module's source with __name__ == '__main__' (covers the guard)."""
    mod = importlib.import_module(module_name)
    src = Path(mod.__file__).read_text()
    exec(compile(src, mod.__file__, "exec"), {"__name__": "__main__", "__file__": mod.__file__})


# ===========================================================================
# npm_package_installer.py
# ===========================================================================

class TestNpmPackageInstallerInit:
    def test_init_stores_key(self):
        inst = NpmPackageInstaller(snyk_api_key="k1")
        assert inst._snyk_api_key == "k1"
        assert inst._client is None and inst._scanner is None
        assert inst._script_analyzer is None and inst._sandbox is None

    def test_client_lazy_loads(self):
        with patch("docker.from_env") as from_env:
            inst = NpmPackageInstaller()
            assert inst.client is from_env.return_value
            assert inst.client is from_env.return_value
            assert from_env.call_count == 1

    def test_scanner_lazy_loads_with_key(self):
        with patch("core.npm_package_installer.NpmDependencyScanner") as cls:
            inst = NpmPackageInstaller(snyk_api_key="sk")
            assert inst.scanner is cls.return_value
            assert inst.scanner is cls.return_value
            cls.assert_called_once_with(sny_api_key="sk")

    def test_script_analyzer_lazy_loads(self):
        with patch("core.npm_package_installer.NpmScriptAnalyzer") as cls:
            inst = NpmPackageInstaller()
            assert inst.script_analyzer is cls.return_value
            assert inst.script_analyzer is cls.return_value
            cls.assert_called_once_with()

    def test_sandbox_lazy_loads(self):
        with patch("core.npm_package_installer.HazardSandbox") as cls:
            inst = NpmPackageInstaller()
            assert inst.sandbox is cls.return_value
            assert inst.sandbox is cls.return_value
            cls.assert_called_once_with()


class TestNpmInstallPackages:
    def _env(self):
        client = MagicMock()
        scanner = MagicMock()
        sa = MagicMock()
        sa.analyze_package_scripts.return_value = {
            "malicious": False, "warnings": [], "details": [], "scripts_found": [],
        }
        return patch("docker.from_env", return_value=client), client, scanner, sa

    def _make(self):
        c = MagicMock()
        s = MagicMock()
        a = MagicMock()
        a.analyze_package_scripts.return_value = {
            "malicious": False, "warnings": [], "details": [], "scripts_found": [],
        }
        return c, s, a

    def test_malicious_scripts_blocked(self):
        client, scanner, sa = self._make()
        sa.analyze_package_scripts.return_value = {
            "malicious": True, "warnings": ["postinstall found"], "details": [], "scripts_found": [],
        }
        with patch("docker.from_env", return_value=client), \
                patch("core.npm_package_installer.NpmScriptAnalyzer", return_value=sa):
            inst = NpmPackageInstaller()
            result = inst.install_packages("skill", ["evil@1.0.0"])
        assert result["success"] is False
        assert "Malicious" in result["error"]
        assert result["image_tag"] is None

    def test_suspicious_warnings_but_continues(self):
        client, scanner, sa = self._make()
        sa.analyze_package_scripts.return_value = {
            "malicious": False, "warnings": ["suspicious combo"], "details": [], "scripts_found": [],
        }
        with patch("docker.from_env", return_value=client), \
                patch("core.npm_package_installer.NpmScriptAnalyzer", return_value=sa):
            inst = NpmPackageInstaller()
            result = inst.install_packages("skill", [], scan_for_vulnerabilities=False)
        assert result["success"] is True
        assert result["warning"] == "No packages specified"

    def test_empty_packages(self):
        client, scanner, sa = self._make()
        with patch("docker.from_env", return_value=client), \
                patch("core.npm_package_installer.NpmScriptAnalyzer", return_value=sa):
            inst = NpmPackageInstaller()
            result = inst.install_packages("skill", [])
        assert result["success"] is True
        assert result["image_tag"] is None
        assert result["vulnerabilities"] == []

    def test_scan_safe_then_builds(self):
        client, scanner, sa = self._make()
        scanner.scan_packages.return_value = {"safe": True, "vulnerabilities": []}
        mock_image = MagicMock()
        client.images.build.return_value = (mock_image, iter([{"stream": "Step 1"}]))
        with patch("docker.from_env", return_value=client), \
                patch("core.npm_package_installer.NpmScriptAnalyzer", return_value=sa), \
                patch("core.npm_package_installer.NpmDependencyScanner", return_value=scanner):
            inst = NpmPackageInstaller()
            result = inst.install_packages("skill", ["lodash@4.17.21"])
        assert result["success"] is True
        assert result["image_tag"] == "atom-npm-skill:skill-v1"
        assert result["build_logs"] == ["Step 1"]
        scanner.scan_packages.assert_called_once_with(["lodash@4.17.21"], "npm")

    def test_scan_unsafe_blocks(self):
        client, scanner, sa = self._make()
        scanner.scan_packages.return_value = {
            "safe": False, "vulnerabilities": [{"cve_id": "CVE-1"}],
        }
        with patch("docker.from_env", return_value=client), \
                patch("core.npm_package_installer.NpmScriptAnalyzer", return_value=sa), \
                patch("core.npm_package_installer.NpmDependencyScanner", return_value=scanner):
            inst = NpmPackageInstaller()
            result = inst.install_packages("skill", ["lodash@4.17.21"])
        assert result["success"] is False
        assert result["image_tag"] is None
        assert result["vulnerabilities"] == [{"cve_id": "CVE-1"}]

    def test_build_exception_returns_failure(self):
        client, scanner, sa = self._make()
        client.images.build.side_effect = RuntimeError("build exploded")
        with patch("docker.from_env", return_value=client), \
                patch("core.npm_package_installer.NpmScriptAnalyzer", return_value=sa):
            inst = NpmPackageInstaller()
            result = inst.install_packages("skill", ["lodash@4.17.21"], scan_for_vulnerabilities=False)
        assert result["success"] is False
        assert result["error"] == "build exploded"


class TestNpmCreatePackageJson:
    def test_scoped_with_version(self):
        inst = NpmPackageInstaller()
        result = inst._create_package_json(["@scope/name@1.2.3"])
        assert result["dependencies"] == {"@scope/name": "1.2.3"}

    def test_scoped_without_version(self):
        inst = NpmPackageInstaller()
        result = inst._create_package_json(["@scope/name"])
        assert result["dependencies"] == {"@scope/name": "*"}

    def test_regular_with_version(self):
        inst = NpmPackageInstaller()
        result = inst._create_package_json(["lodash@4.17.21"])
        assert result["dependencies"] == {"lodash": "4.17.21"}

    def test_regular_without_version(self):
        inst = NpmPackageInstaller()
        result = inst._create_package_json(["axios"])
        assert result["dependencies"] == {"axios": "*"}
        assert result["private"] is True


class TestNpmGenerateDockerfile:
    def test_npm(self):
        dockerfile = NpmPackageInstaller()._generate_dockerfile(
            {"name": "x"}, "npm", "node:20-alpine")
        assert "npm ci --omit=dev --ignore-scripts" in dockerfile
        assert "FROM node:20-alpine" in dockerfile
        assert "USER nodejs" in dockerfile

    def test_yarn(self):
        dockerfile = NpmPackageInstaller()._generate_dockerfile(
            {"name": "x"}, "yarn", "node:20-alpine")
        assert "yarn install --production --ignore-scripts" in dockerfile

    def test_pnpm(self):
        dockerfile = NpmPackageInstaller()._generate_dockerfile(
            {"name": "x"}, "pnpm", "node:20-alpine")
        assert "pnpm install --prod --ignore-scripts" in dockerfile

    def test_unknown_manager_raises(self):
        with pytest.raises(ValueError, match="Unknown package manager"):
            NpmPackageInstaller()._generate_dockerfile({"name": "x"}, "bun", "node:20-alpine")


class TestNpmBuildSkillImage:
    def _inst(self, client):
        inst = NpmPackageInstaller()
        inst._client = client
        return inst

    def test_build_collects_stream_logs(self, tmp_path, monkeypatch):
        client = MagicMock()
        logs = [
            {"stream": "  Step 1/4 : FROM node:20-alpine  "},
            {"stream": ""},
            {"aux": {"ID": "abc"}},
            {"stream": "Successfully built abc123"},
        ]
        client.images.build.return_value = (MagicMock(), iter(logs))
        inst = self._inst(client)
        result = inst._build_skill_image("skill", ["lodash@4.17.21"], "tag", "npm", "node:20-alpine")
        assert result == ["Step 1/4 : FROM node:20-alpine", "Successfully built abc123"]
        assert client.images.build.call_args.kwargs["tag"] == "tag"

    def test_cleanup_failure_logs_warning(self, tmp_path, monkeypatch):
        client = MagicMock()
        client.images.build.return_value = (MagicMock(), iter([]))
        with patch("core.npm_package_installer.shutil.rmtree", side_effect=OSError("locked")):
            inst = self._inst(client)
            result = inst._build_skill_image("skill", ["x@1"], "tag", "npm", "node:20-alpine")
        assert result == []


class TestNpmExecuteWithPackages:
    def test_image_found_executes(self):
        client = MagicMock()
        sandbox = MagicMock()
        sandbox.execute_nodejs.return_value = "node output"
        with patch("docker.from_env", return_value=client), \
                patch("core.npm_package_installer.HazardSandbox", return_value=sandbox):
            inst = NpmPackageInstaller()
            result = inst.execute_with_packages("my/skill", "code", {"a": 1})
        assert result == "node output"
        client.images.get.assert_called_once_with("atom-npm-skill:my-skill-v1")
        sandbox.execute_nodejs.assert_called_once_with(
            code="code", inputs={"a": 1}, timeout_seconds=30,
            memory_limit="256m", cpu_limit=0.5, image="atom-npm-skill:my-skill-v1")

    def test_image_not_found_raises(self):
        client = MagicMock()
        client.images.get.side_effect = docker.errors.ImageNotFound("nope")
        with patch("docker.from_env", return_value=client):
            inst = NpmPackageInstaller()
            with pytest.raises(RuntimeError, match="not found"):
                inst.execute_with_packages("my/skill", "code", {})


class TestNpmCleanupAndList:
    def test_cleanup_success(self):
        client = MagicMock()
        with patch("docker.from_env", return_value=client):
            inst = NpmPackageInstaller()
            assert inst.cleanup_skill_image("skill") is True
        client.images.get.return_value.remove.assert_called_once_with(force=True)

    def test_cleanup_not_found(self):
        client = MagicMock()
        client.images.get.side_effect = docker.errors.ImageNotFound("nope")
        with patch("docker.from_env", return_value=client):
            inst = NpmPackageInstaller()
            assert inst.cleanup_skill_image("skill") is False

    def test_cleanup_generic_error(self):
        client = MagicMock()
        client.images.get.side_effect = RuntimeError("daemon down")
        with patch("docker.from_env", return_value=client):
            inst = NpmPackageInstaller()
            assert inst.cleanup_skill_image("skill") is False

    def test_get_skill_images_filters(self):
        client = MagicMock()
        matching = SimpleNamespace(
            tags=["atom-npm-skill:s1-v1"], id="img1",
            attrs={"Size": 1024, "Created": "2026-01-01"})
        other = SimpleNamespace(tags=["other:latest"], id="img2", attrs={})
        no_tags = SimpleNamespace(tags=[], id="img3", attrs={})
        client.images.list.return_value = [matching, other, no_tags]
        with patch("docker.from_env", return_value=client):
            inst = NpmPackageInstaller()
            result = inst.get_skill_images()
        assert len(result) == 1
        assert result[0]["tags"] == ["atom-npm-skill:s1-v1"]
        assert result[0]["size"] == 1024
        assert result[0]["created"] == "2026-01-01"

    def test_get_skill_images_error(self):
        client = MagicMock()
        client.images.list.side_effect = RuntimeError("boom")
        with patch("docker.from_env", return_value=client):
            inst = NpmPackageInstaller()
            assert inst.get_skill_images() == []


class TestNpmTestInstallerBasic:
    def test_success_flow(self):
        client = MagicMock()
        client.images.build.return_value = (MagicMock(), iter([]))
        with patch("docker.from_env", return_value=client), \
                patch("core.npm_script_analyzer.NpmScriptAnalyzer") as sa_cls:
            sa_cls.return_value.analyze_package_scripts.return_value = {
                "malicious": False, "warnings": [], "details": [], "scripts_found": [],
            }
            from core.npm_package_installer import test_installer_basic
            assert test_installer_basic() is True

    def test_cleanup_warning_path(self):
        client = MagicMock()
        client.images.build.return_value = (MagicMock(), iter([]))
        client.images.get.side_effect = docker.errors.ImageNotFound("gone")
        with patch("docker.from_env", return_value=client), \
                patch("core.npm_script_analyzer.NpmScriptAnalyzer") as sa_cls:
            sa_cls.return_value.analyze_package_scripts.return_value = {
                "malicious": False, "warnings": [], "details": [], "scripts_found": [],
            }
            from core.npm_package_installer import test_installer_basic
            assert test_installer_basic() is True

    def test_install_failure_path(self):
        client = MagicMock()
        client.images.build.side_effect = RuntimeError("no daemon")
        with patch("docker.from_env", return_value=client), \
                patch("core.npm_script_analyzer.NpmScriptAnalyzer") as sa_cls:
            sa_cls.return_value.analyze_package_scripts.return_value = {
                "malicious": False, "warnings": [], "details": [], "scripts_found": [],
            }
            from core.npm_package_installer import test_installer_basic
            assert test_installer_basic() is False

    def test_outer_exception_path(self):
        with patch("docker.from_env", side_effect=RuntimeError("no docker")), \
                patch("core.npm_script_analyzer.NpmScriptAnalyzer"):
            from core.npm_package_installer import test_installer_basic
            assert test_installer_basic() is False

    def test_constructor_exception_path(self):
        with patch("core.npm_package_installer.NpmPackageInstaller",
                   side_effect=RuntimeError("constructor blew up")):
            from core.npm_package_installer import test_installer_basic
            assert test_installer_basic() is False

    def test_main_guard(self):
        client = MagicMock()
        client.images.build.return_value = (MagicMock(), iter([]))
        with patch("docker.from_env", return_value=client), \
                patch("core.npm_script_analyzer.NpmScriptAnalyzer") as sa_cls:
            sa_cls.return_value.analyze_package_scripts.return_value = {
                "malicious": False, "warnings": [], "details": [], "scripts_found": [],
            }
            _exec_module_as_main("core.npm_package_installer")


# ===========================================================================
# package_dependency_scanner.py
# ===========================================================================

class TestPackageDependencyScanner:
    def test_init_with_key(self):
        assert PackageDependencyScanner(safety_api_key="sk").safety_api_key == "sk"

    def test_init_from_env(self, monkeypatch):
        monkeypatch.setenv("SAFETY_API_KEY", "env-key")
        assert PackageDependencyScanner().safety_api_key == "env-key"

    def test_scan_empty_requirements(self):
        result = PackageDependencyScanner().scan_packages([])
        assert result == {"safe": True, "vulnerabilities": [], "dependency_tree": {}, "conflicts": []}

    def test_scan_all_non_strings(self):
        result = PackageDependencyScanner().scan_packages([None, 42, ["x"]])
        assert result == {"safe": True, "vulnerabilities": [], "dependency_tree": {}, "conflicts": []}

    def _side_effect(self, dep_rc=0, dep_out="[]", audit_rc=0, audit_out="",
                     safety_rc=0, safety_out="", timeout_for=None, raise_for=None):
        def effect(cmd, **kw):
            if timeout_for and cmd[0] == timeout_for:
                raise subprocess.TimeoutExpired(cmd, 120)
            if raise_for and cmd[0] == raise_for:
                raise RuntimeError("boom")
            if cmd[0] == "pip":
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            if cmd[0] == "pipdeptree":
                return SimpleNamespace(returncode=dep_rc, stdout=dep_out, stderr="tree failed")
            if cmd[0] == "pip-audit":
                return SimpleNamespace(returncode=audit_rc, stdout=audit_out, stderr="")
            if cmd[0] == "safety":
                return SimpleNamespace(returncode=safety_rc, stdout=safety_out, stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return effect

    TREE = json.dumps([{
        "package": {"package_name": "numpy", "installed_version": "1.21.0"},
        "dependencies": [{"package_name": "pandas", "installed_version": "2.0.0"}],
    }])

    AUDIT_VULN = json.dumps([{
        "id": "CVE-2021-23337", "fix_versions": ["1.0.1"], "name": "lodash",
        "versions": ["4.17.20"], "description": "prototype pollution",
    }])

    SAFETY_VULN = json.dumps([{
        "id": "S-1", "vulnerability_id": "44715", "package_name": "requests",
        "affected_versions": ["<2.31.0"], "advisory": "advisory text",
    }])

    def test_scan_clean(self):
        with patch("core.package_dependency_scanner.subprocess.run",
                   side_effect=self._side_effect(dep_out=self.TREE)):
            result = PackageDependencyScanner().scan_packages(["numpy==1.21.0"])
        assert result["safe"] is True
        assert result["vulnerabilities"] == []
        assert result["dependency_tree"]["numpy"]["version"] == "1.21.0"
        assert result["dependency_tree"]["numpy"]["dependencies"] == {"pandas": "2.0.0"}

    def test_scan_with_safety_key_and_vulnerabilities(self):
        with patch("core.package_dependency_scanner.subprocess.run",
                   side_effect=self._side_effect(
                       audit_rc=1, audit_out=self.AUDIT_VULN,
                       safety_rc=1, safety_out=self.SAFETY_VULN)):
            result = PackageDependencyScanner(safety_api_key="sk").scan_packages(["lodash"])
        assert result["safe"] is False
        assert result["vulnerabilities"][0]["cve_id"] == "CVE-2021-23337"
        assert result["vulnerabilities"][0]["severity"] == "1.0.1"
        assert result["vulnerabilities"][0]["source"] == "pip-audit"
        assert result["vulnerabilities"][1]["cve_id"] == "S-1"
        assert result["vulnerabilities"][1]["source"] == "safety"

    def test_audit_bad_json(self):
        with patch("core.package_dependency_scanner.subprocess.run",
                   side_effect=self._side_effect(audit_rc=1, audit_out="not json")):
            result = PackageDependencyScanner().scan_packages(["lodash"])
        assert result["safe"] is True
        assert result["vulnerabilities"] == []

    def test_audit_timeout(self):
        with patch("core.package_dependency_scanner.subprocess.run",
                   side_effect=self._side_effect(timeout_for="pip-audit")):
            result = PackageDependencyScanner().scan_packages(["lodash"])
        assert result["safe"] is True

    def test_audit_generic_error(self):
        with patch("core.package_dependency_scanner.subprocess.run",
                   side_effect=self._side_effect(raise_for="pip-audit")):
            result = PackageDependencyScanner().scan_packages(["lodash"])
        assert result["safe"] is True

    def test_safety_clean_result(self):
        with patch("core.package_dependency_scanner.subprocess.run",
                   side_effect=self._side_effect(safety_rc=0, safety_out="")):
            result = PackageDependencyScanner(safety_api_key="sk").scan_packages(["lodash"])
        assert result["vulnerabilities"] == []
        assert result["safe"] is True

    def test_safety_bad_json(self):
        with patch("core.package_dependency_scanner.subprocess.run",
                   side_effect=self._side_effect(safety_rc=1, safety_out="garbage")):
            result = PackageDependencyScanner(safety_api_key="sk").scan_packages(["lodash"])
        assert result["vulnerabilities"] == []

    def test_safety_timeout(self):
        with patch("core.package_dependency_scanner.subprocess.run",
                   side_effect=self._side_effect(timeout_for="safety")):
            result = PackageDependencyScanner(safety_api_key="sk").scan_packages(["lodash"])
        assert result["safe"] is True

    def test_safety_generic_error(self):
        with patch("core.package_dependency_scanner.subprocess.run",
                   side_effect=self._side_effect(raise_for="safety")):
            result = PackageDependencyScanner(safety_api_key="sk").scan_packages(["lodash"])
        assert result["safe"] is True

    def test_pipdeptree_failure_rc(self):
        with patch("core.package_dependency_scanner.subprocess.run",
                   side_effect=self._side_effect(dep_rc=1, dep_out="")):
            result = PackageDependencyScanner().scan_packages(["numpy"])
        assert result["dependency_tree"] == {}

    def test_pipdeptree_timeout(self):
        with patch("core.package_dependency_scanner.subprocess.run",
                   side_effect=self._side_effect(timeout_for="pipdeptree")):
            result = PackageDependencyScanner().scan_packages(["numpy"])
        assert result["dependency_tree"] == {}

    def test_pipdeptree_generic_error(self):
        with patch("core.package_dependency_scanner.subprocess.run",
                   side_effect=self._side_effect(raise_for="pipdeptree")):
            result = PackageDependencyScanner().scan_packages(["numpy"])
        assert result["dependency_tree"] == {}

    def test_pipdeptree_bad_json(self):
        with patch("core.package_dependency_scanner.subprocess.run",
                   side_effect=self._side_effect(dep_rc=0, dep_out="not json")):
            result = PackageDependencyScanner().scan_packages(["numpy"])
        assert result["dependency_tree"] == {}

    def test_temp_file_cleanup_error(self):
        with patch("core.package_dependency_scanner.subprocess.run",
                   side_effect=self._side_effect()), \
                patch("core.package_dependency_scanner.os.unlink", side_effect=OSError("busy")):
            result = PackageDependencyScanner().scan_packages(["numpy"])
        assert result["safe"] is True

    def test_version_conflict(self):
        tree = {
            "main": {"version": "1.0", "dependencies": {"dep": "1.0"}},
            "dep": {"version": "2.0", "dependencies": {}},
        }
        conflicts = PackageDependencyScanner()._check_version_conflicts(tree)
        assert len(conflicts) == 1
        assert conflicts[0]["severity"] == "version_conflict"
        assert conflicts[0]["package"] == "dep"

    def test_transitive_conflict(self):
        tree = {
            "a": {"version": "1.0", "dependencies": {"b": "1.0"}},
            "c": {"version": "1.0", "dependencies": {"b": "2.0"}},
        }
        conflicts = PackageDependencyScanner()._check_version_conflicts(tree)
        assert len(conflicts) == 1
        assert conflicts[0]["severity"] == "transitive_conflict"
        assert conflicts[0]["package"] == "b"

    def test_no_conflicts(self):
        tree = {
            "a": {"version": "1.0", "dependencies": {"b": "1.0"}},
            "b": {"version": "1.0", "dependencies": {}},
        }
        assert PackageDependencyScanner()._check_version_conflicts(tree) == []

    def test_scan_with_conflicts_marks_unsafe(self):
        tree = {
            "a": {"version": "1.0", "dependencies": {"b": "1.0"}},
            "b": {"version": "2.0", "dependencies": {}},
        }
        with patch.object(PackageDependencyScanner, "_build_dependency_tree", return_value=tree), \
                patch.object(PackageDependencyScanner, "_run_pip_audit",
                             return_value={"vulnerabilities": []}):
            result = PackageDependencyScanner().scan_packages(["a"])
        assert result["safe"] is False
        assert len(result["conflicts"]) == 1


# ===========================================================================
# package_installer.py
# ===========================================================================

class TestPackageInstaller:
    def test_init_stores_key(self):
        inst = PackageInstaller(safety_api_key="k1")
        assert inst._safety_api_key == "k1"

    def test_client_lazy_loads(self):
        with patch("docker.from_env") as from_env:
            inst = PackageInstaller()
            assert inst.client is from_env.return_value
            assert inst.client is from_env.return_value
            assert from_env.call_count == 1

    def test_scanner_lazy_loads_with_key(self):
        with patch("core.package_installer.PackageDependencyScanner") as cls:
            inst = PackageInstaller(safety_api_key="sk")
            assert inst.scanner is cls.return_value
            assert inst.scanner is cls.return_value
            cls.assert_called_once_with(safety_api_key="sk")

    def test_sandbox_lazy_loads(self):
        with patch("core.package_installer.HazardSandbox") as cls:
            inst = PackageInstaller()
            assert inst.sandbox is cls.return_value
            assert inst.sandbox is cls.return_value
            cls.assert_called_once_with()

    def _make(self):
        client = MagicMock()
        scanner = MagicMock()
        return client, scanner

    def test_install_scan_safe(self):
        client, scanner = self._make()
        scanner.scan_packages.return_value = {"safe": True, "vulnerabilities": []}
        client.images.build.return_value = (MagicMock(), iter([{"stream": "Step 1"}]))
        with patch("docker.from_env", return_value=client), \
                patch("core.package_installer.PackageDependencyScanner", return_value=scanner):
            inst = PackageInstaller()
            result = inst.install_packages("skill", ["numpy==1.21.0"])
        assert result["success"] is True
        assert result["image_tag"] == "atom-skill:skill-v1"
        assert result["build_logs"] == ["Step 1"]
        scanner.scan_packages.assert_called_once_with(["numpy==1.21.0"])

    def test_install_scan_unsafe(self):
        client, scanner = self._make()
        scanner.scan_packages.return_value = {
            "safe": False, "vulnerabilities": [{"cve_id": "CVE-1"}],
        }
        with patch("docker.from_env", return_value=client), \
                patch("core.package_installer.PackageDependencyScanner", return_value=scanner):
            inst = PackageInstaller()
            result = inst.install_packages("skill", ["numpy==1.21.0"])
        assert result["success"] is False
        assert "Vulnerabilities" in result["error"]
        assert result["image_tag"] is None

    def test_install_no_scan(self):
        client, scanner = self._make()
        client.images.build.return_value = (MagicMock(), iter([]))
        with patch("docker.from_env", return_value=client), \
                patch("core.package_installer.PackageDependencyScanner", return_value=scanner):
            inst = PackageInstaller()
            result = inst.install_packages("skill", ["numpy==1.21.0"], scan_for_vulnerabilities=False)
        assert result["success"] is True
        scanner.scan_packages.assert_not_called()

    def test_install_build_exception(self):
        client, scanner = self._make()
        client.images.build.side_effect = RuntimeError("no daemon")
        with patch("docker.from_env", return_value=client), \
                patch("core.package_installer.PackageDependencyScanner", return_value=scanner):
            inst = PackageInstaller()
            result = inst.install_packages("skill", ["numpy==1.21.0"], scan_for_vulnerabilities=False)
        assert result["success"] is False
        assert result["error"] == "no daemon"

    def test_build_skill_image_happy(self):
        client, scanner = self._make()
        client.images.build.return_value = (
            MagicMock(), iter([{"stream": "Step 1"}, {"stream": ""}, {"aux": {}}]))
        with patch("docker.from_env", return_value=client):
            inst = PackageInstaller()
            logs = inst._build_skill_image("skill", ["numpy==1.21.0"], "tag", "python:3.11-slim")
        assert logs == ["Step 1"]

    def test_build_skill_image_cleanup_error(self):
        client, scanner = self._make()
        client.images.build.return_value = (MagicMock(), iter([]))
        with patch("docker.from_env", return_value=client), \
                patch("core.package_installer.shutil.rmtree", side_effect=OSError("locked")):
            inst = PackageInstaller()
            logs = inst._build_skill_image("skill", ["numpy==1.21.0"], "tag", "python:3.11-slim")
        assert logs == []

    def test_execute_image_found(self):
        client, scanner = self._make()
        sandbox = MagicMock()
        sandbox.execute_python.return_value = "out"
        with patch("docker.from_env", return_value=client), \
                patch("core.package_installer.HazardSandbox", return_value=sandbox):
            inst = PackageInstaller()
            result = inst.execute_with_packages("my/skill", "code", {"a": 1})
        assert result == "out"
        client.images.get.assert_called_once_with("atom-skill:my-skill-v1")
        sandbox.execute_python.assert_called_once_with(
            code="code", inputs={"a": 1}, timeout_seconds=30,
            memory_limit="256m", cpu_limit=0.5, image="atom-skill:my-skill-v1")

    def test_execute_image_not_found(self):
        client, scanner = self._make()
        client.images.get.side_effect = docker.errors.ImageNotFound("nope")
        with patch("docker.from_env", return_value=client):
            inst = PackageInstaller()
            with pytest.raises(RuntimeError, match="not found"):
                inst.execute_with_packages("my/skill", "code", {})

    def test_cleanup_success(self):
        client, scanner = self._make()
        with patch("docker.from_env", return_value=client):
            inst = PackageInstaller()
            assert inst.cleanup_skill_image("skill") is True
        client.images.get.return_value.remove.assert_called_once_with(force=True)

    def test_cleanup_not_found(self):
        client, scanner = self._make()
        client.images.get.side_effect = docker.errors.ImageNotFound("nope")
        with patch("docker.from_env", return_value=client):
            inst = PackageInstaller()
            assert inst.cleanup_skill_image("skill") is False

    def test_cleanup_generic_error(self):
        client, scanner = self._make()
        client.images.get.side_effect = RuntimeError("daemon down")
        with patch("docker.from_env", return_value=client):
            inst = PackageInstaller()
            assert inst.cleanup_skill_image("skill") is False

    def test_get_skill_images(self):
        client, scanner = self._make()
        matching = SimpleNamespace(
            tags=["atom-skill:s1-v1"], id="img1", attrs={"Size": 512, "Created": "2026-01-01"})
        other = SimpleNamespace(tags=["other:latest"], id="img2", attrs={})
        client.images.list.return_value = [matching, other]
        with patch("docker.from_env", return_value=client):
            inst = PackageInstaller()
            result = inst.get_skill_images()
        assert len(result) == 1
        assert result[0]["size"] == 512

    def test_get_skill_images_error(self):
        client, scanner = self._make()
        client.images.list.side_effect = RuntimeError("boom")
        with patch("docker.from_env", return_value=client):
            inst = PackageInstaller()
            assert inst.get_skill_images() == []

    def test_installer_basic_success(self):
        client, scanner = self._make()
        client.images.build.return_value = (MagicMock(), iter([]))
        with patch("docker.from_env", return_value=client):
            from core.package_installer import test_installer_basic
            assert test_installer_basic() is True

    def test_installer_basic_cleanup_warning(self):
        client, scanner = self._make()
        client.images.build.return_value = (MagicMock(), iter([]))
        client.images.get.side_effect = docker.errors.ImageNotFound("gone")
        with patch("docker.from_env", return_value=client):
            from core.package_installer import test_installer_basic
            assert test_installer_basic() is True

    def test_installer_basic_install_failure(self):
        client, scanner = self._make()
        client.images.build.side_effect = RuntimeError("no daemon")
        with patch("docker.from_env", return_value=client):
            from core.package_installer import test_installer_basic
            assert test_installer_basic() is False

    def test_installer_basic_outer_exception(self):
        with patch("docker.from_env", side_effect=RuntimeError("no docker")):
            from core.package_installer import test_installer_basic
            assert test_installer_basic() is False

    def test_installer_basic_constructor_exception(self):
        with patch("core.package_installer.PackageInstaller",
                   side_effect=RuntimeError("constructor blew up")):
            from core.package_installer import test_installer_basic
            assert test_installer_basic() is False

    def test_main_guard(self):
        client, scanner = self._make()
        client.images.build.return_value = (MagicMock(), iter([]))
        with patch("docker.from_env", return_value=client):
            _exec_module_as_main("core.package_installer")


# ===========================================================================
# skill_dynamic_loader.py
# ===========================================================================

class TestSkillDynamicLoader:
    def test_init_with_and_without_dir(self, tmp_path):
        loader = SkillDynamicLoader()
        assert loader.skills_dir is None
        assert loader.loaded_skills == {} and loader.skill_versions == {}
        loader2 = SkillDynamicLoader(skills_dir=str(tmp_path))
        assert loader2.skills_dir == tmp_path

    def _write_skill(self, tmp_path, name="greet", body="def run(inputs):\n    return 'hi'\n"):
        p = tmp_path / f"{name}.py"
        p.write_text(body)
        return p

    def test_load_skill_success(self, tmp_path):
        loader = SkillDynamicLoader(skills_dir=str(tmp_path))
        p = self._write_skill(tmp_path)
        module = loader.load_skill("greet", str(p))
        assert module is not None
        assert module.run({}) == "hi"
        assert "greet" in loader.loaded_skills
        assert "greet" in loader.skill_versions

    def test_load_skill_cached(self, tmp_path):
        loader = SkillDynamicLoader(skills_dir=str(tmp_path))
        p = self._write_skill(tmp_path)
        first = loader.load_skill("greet", str(p))
        second = loader.load_skill("greet", str(p))
        assert first is second

    def test_load_skill_force_reload(self, tmp_path):
        loader = SkillDynamicLoader(skills_dir=str(tmp_path))
        p = self._write_skill(tmp_path)
        first = loader.load_skill("greet", str(p))
        p.write_text("def run(inputs):\n    return 'changed'\n")
        second = loader.load_skill("greet", str(p), force_reload=True)
        assert second is not first
        assert second.run({}) == "changed"

    def test_load_skill_file_not_found(self, tmp_path):
        loader = SkillDynamicLoader(skills_dir=str(tmp_path))
        assert loader.load_skill("missing", str(tmp_path / "nope.py")) is None

    def test_load_skill_outside_skills_dir(self, tmp_path):
        loader = SkillDynamicLoader(skills_dir=str(tmp_path))
        outside = Path(tempfile.mkdtemp()) / "evil.py"
        outside.write_text("def run(inputs):\n    return 'pwned'\n")
        try:
            assert loader.load_skill("evil", str(outside)) is None
        finally:
            outside.unlink()

    def test_load_skill_without_skills_dir_allows_any_path(self, tmp_path):
        loader = SkillDynamicLoader()
        p = self._write_skill(tmp_path)
        assert loader.load_skill("anywhere", str(p)) is not None

    def test_load_skill_spec_none(self, tmp_path):
        loader = SkillDynamicLoader(skills_dir=str(tmp_path))
        p = self._write_skill(tmp_path)
        with patch("core.skill_dynamic_loader.importlib.util.spec_from_file_location",
                   return_value=None):
            assert loader.load_skill("greet", str(p)) is None

    def test_load_skill_exec_error_cleans_sys_modules(self, tmp_path):
        loader = SkillDynamicLoader(skills_dir=str(tmp_path))
        p = self._write_skill(tmp_path)
        spec = SimpleNamespace(name="greet", loader=MagicMock())
        spec.loader.exec_module.side_effect = RuntimeError("boom")
        with patch("core.skill_dynamic_loader.importlib.util.spec_from_file_location",
                   return_value=spec):
            assert loader.load_skill("greet", str(p)) is None
        assert "greet" not in sys.modules
        assert "greet" not in loader.loaded_skills

    def test_reload_skill_not_loaded(self, tmp_path):
        loader = SkillDynamicLoader(skills_dir=str(tmp_path))
        assert loader.reload_skill("never") is None

    def test_reload_skill_unchanged(self, tmp_path):
        loader = SkillDynamicLoader(skills_dir=str(tmp_path))
        p = self._write_skill(tmp_path)
        module = loader.load_skill("greet", str(p))
        assert loader.reload_skill("greet") is module

    def test_reload_skill_changed(self, tmp_path):
        loader = SkillDynamicLoader(skills_dir=str(tmp_path))
        p = self._write_skill(tmp_path)
        loader.load_skill("greet", str(p))
        p.write_text("def run(inputs):\n    return 'a much longer second version'\n")
        module = loader.reload_skill("greet")
        assert module.run({}) == "a much longer second version"

    def test_get_skill(self, tmp_path):
        loader = SkillDynamicLoader(skills_dir=str(tmp_path))
        assert loader.get_skill("greet") is None
        p = self._write_skill(tmp_path)
        module = loader.load_skill("greet", str(p))
        assert loader.get_skill("greet") is module

    def test_unload_skill(self, tmp_path):
        loader = SkillDynamicLoader(skills_dir=str(tmp_path))
        assert loader.unload_skill("greet") is False
        p = self._write_skill(tmp_path)
        loader.load_skill("greet", str(p))
        assert loader.unload_skill("greet") is True
        assert "greet" not in loader.loaded_skills
        assert "greet" not in loader.skill_versions

    def test_list_loaded_skills(self, tmp_path):
        loader = SkillDynamicLoader(skills_dir=str(tmp_path))
        p = self._write_skill(tmp_path)
        loader.load_skill("greet", str(p))
        listing = loader.list_loaded_skills()
        assert listing["greet"]["path"] == str(p)
        assert listing["greet"]["hash"] == loader.skill_versions["greet"][:8]

    def test_check_for_updates(self, tmp_path):
        loader = SkillDynamicLoader(skills_dir=str(tmp_path))
        p = self._write_skill(tmp_path)
        loader.load_skill("greet", str(p))
        assert loader.check_for_updates() == {"greet": False}
        p.write_text("def run(inputs):\n    return 'a longer updated version'\n")
        assert loader.check_for_updates() == {"greet": True}

    def test_calculate_file_hash_error(self, tmp_path):
        loader = SkillDynamicLoader(skills_dir=str(tmp_path))
        assert loader._calculate_file_hash(tmp_path / "ghost.py") == ""

    def test_calculate_file_hash_success(self, tmp_path):
        p = self._write_skill(tmp_path)
        assert len(SkillDynamicLoader()._calculate_file_hash(p)) == 64

    def test_start_file_monitor_happy(self, tmp_path, monkeypatch):
        events = types.ModuleType("watchdog.events")
        obs = types.ModuleType("watchdog.observers")

        class FakeObserver:
            def __init__(self):
                self.scheduled = []
                self.started = False
                self.stopped = False
                self.joined = False

            def schedule(self, handler, path, recursive):
                self.scheduled.append((handler, path, recursive))

            def start(self):
                self.started = True

            def stop(self):
                self.stopped = True

            def join(self):
                self.joined = True

        events.FileSystemEventHandler = type("FileSystemEventHandler", (), {})
        obs.Observer = FakeObserver
        monkeypatch.setitem(sys.modules, "watchdog", types.ModuleType("watchdog"))
        monkeypatch.setitem(sys.modules, "watchdog.events", events)
        monkeypatch.setitem(sys.modules, "watchdog.observers", obs)

        loader = SkillDynamicLoader(skills_dir=str(tmp_path), enable_monitoring=True)
        assert isinstance(loader._observer, FakeObserver)
        assert len(loader._observer.scheduled) == 1
        handler, path, recursive = loader._observer.scheduled[0]
        assert recursive is True

        p = self._write_skill(tmp_path)
        loader.load_skill("greet", str(p))
        before = loader.skill_versions["greet"]
        p.write_text("def run(inputs):\n    return 'a much longer third version'\n")
        handler.on_modified(SimpleNamespace(src_path=str(p)))
        assert loader.skill_versions["greet"] != before
        handler.on_modified(SimpleNamespace(src_path=str(tmp_path / "notes.txt")))
        handler.on_modified(SimpleNamespace(src_path="/elsewhere/file.py"))

        loader.stop_monitoring()
        assert loader._observer.stopped and loader._observer.joined

    def test_start_file_monitor_import_error(self, tmp_path, monkeypatch):
        monkeypatch.setitem(sys.modules, "watchdog", None)
        loader = SkillDynamicLoader(skills_dir=str(tmp_path), enable_monitoring=True)
        assert loader._observer is None

    def test_start_file_monitor_other_error(self, tmp_path, monkeypatch):
        events = types.ModuleType("watchdog.events")
        obs = types.ModuleType("watchdog.observers")
        events.FileSystemEventHandler = type("FileSystemEventHandler", (), {})

        class BadObserver:
            def schedule(self, *a, **k):
                raise RuntimeError("watch failure")

        obs.Observer = BadObserver
        monkeypatch.setitem(sys.modules, "watchdog", types.ModuleType("watchdog"))
        monkeypatch.setitem(sys.modules, "watchdog.events", events)
        monkeypatch.setitem(sys.modules, "watchdog.observers", obs)
        loader = SkillDynamicLoader(skills_dir=str(tmp_path), enable_monitoring=True)
        assert isinstance(loader._observer, BadObserver)

    def test_stop_monitoring_without_observer(self):
        loader = SkillDynamicLoader()
        loader.stop_monitoring()

    def test_get_global_loader(self, monkeypatch):
        monkeypatch.setattr("core.skill_dynamic_loader._global_loader", None)
        first = get_global_loader()
        second = get_global_loader()
        assert first is second
        assert isinstance(first, SkillDynamicLoader)


# ===========================================================================
# skill_retrieval_service.py
# ===========================================================================

class TestSkillRetrievalService:
    def _registry_mock(self):
        registry = MagicMock()
        registry.list_skills.return_value = [{"skill_id": "s1", "skill_name": "basic"}]
        registry.get_skill.return_value = {
            "skill_name": "data processing skill",
            "description": "processes csv files",
            "tags": ["csv"],
            "skill_body": "Run this skill when you see csv data.\nSecond line.",
        }
        return registry

    def test_flag_off_returns_empty(self):
        with patch("core.skill_retrieval_service.is_skill_injection_enabled",
                   return_value=False):
            result = SkillRetrievalService().retrieve_top_skills(MagicMock(), None, None, "x")
        assert result == ""

    def test_empty_request_returns_empty(self):
        with patch("core.skill_retrieval_service.is_skill_injection_enabled",
                   return_value=True):
            result = SkillRetrievalService().retrieve_top_skills(MagicMock(), None, None, "")
        assert result == ""

    def test_registry_error_returns_empty(self):
        with patch("core.skill_retrieval_service.is_skill_injection_enabled",
                   return_value=True), \
                patch("core.skill_registry_service.SkillRegistryService",
                      side_effect=RuntimeError("db down")):
            result = SkillRetrievalService().retrieve_top_skills(MagicMock(), None, None, "data")
        assert result == ""

    def test_top_skills_formatted(self):
        with patch("core.skill_retrieval_service.is_skill_injection_enabled",
                   return_value=True), \
                patch("core.skill_registry_service.SkillRegistryService") as cls:
            registry = self._registry_mock()
            cls.return_value = registry
            result = SkillRetrievalService().retrieve_top_skills(MagicMock(), None, None,
                                                                 "process csv data", limit=1)
        assert "data processing skill" in result
        assert "processes csv files" in result
        assert "Run this skill when you see csv data." in result
        assert "Only invoke a skill if it directly matches" in result

    def test_no_keyword_overlap_returns_empty(self):
        with patch("core.skill_retrieval_service.is_skill_injection_enabled",
                   return_value=True), \
                patch("core.skill_registry_service.SkillRegistryService") as cls:
            registry = MagicMock()
            registry.list_skills.return_value = [{"skill_id": "s1", "skill_name": "basic"}]
            registry.get_skill.return_value = {
                "skill_name": "basic", "description": "unrelated finance", "tags": [], "skill_body": "",
            }
            cls.return_value = registry
            result = SkillRetrievalService().retrieve_top_skills(
                MagicMock(), None, None, "banana monkey", limit=1)
        assert result == ""

    def test_only_stopwords_returns_empty(self):
        with patch("core.skill_retrieval_service.is_skill_injection_enabled",
                   return_value=True), \
                patch("core.skill_registry_service.SkillRegistryService") as cls:
            registry = MagicMock()
            registry.list_skills.return_value = [{"skill_id": "s1", "skill_name": "basic"}]
            registry.get_skill.return_value = {
                "skill_name": "basic", "description": "x", "tags": [], "skill_body": "",
            }
            cls.return_value = registry
            result = SkillRetrievalService().retrieve_top_skills(
                MagicMock(), None, None, "the of for use i a")
        assert result == ""

    def test_sorting_by_score_then_name(self):
        with patch("core.skill_retrieval_service.is_skill_injection_enabled",
                   return_value=True), \
                patch("core.skill_registry_service.SkillRegistryService") as cls:
            registry = MagicMock()
            registry.list_skills.return_value = [
                {"skill_id": "s1", "skill_name": "alpha"},
                {"skill_id": "s2", "skill_name": "beta"},
            ]
            def get_skill(sid):
                return {
                    "skill_id": sid,
                    "skill_name": "alpha" if sid == "s1" else "beta",
                    "description": "alpha deals with data processing",
                    "tags": [],
                    "skill_body": "",
                }
            registry.get_skill.side_effect = get_skill
            cls.return_value = registry
            result = SkillRetrievalService().retrieve_top_skills(
                MagicMock(), None, None, "data alpha", limit=2)
        assert result.index("alpha") < result.index("beta")

    def test_missing_detail_fields_fallbacks(self):
        with patch("core.skill_retrieval_service.is_skill_injection_enabled",
                   return_value=True), \
                patch("core.skill_registry_service.SkillRegistryService") as cls:
            registry = MagicMock()
            registry.list_skills.return_value = [{"skill_id": "s1", "skill_name": "basic"}]
            registry.get_skill.return_value = {}
            cls.return_value = registry
            result = SkillRetrievalService().retrieve_top_skills(
                MagicMock(), None, None, "basic")
        assert "basic" in result
        assert "No description" in result

    def test_fetch_detail_exception_fallback(self):
        registry = MagicMock()
        registry.get_skill.side_effect = RuntimeError("boom")
        fallback = SkillRetrievalService._fetch_detail(registry, {"skill_id": "s1", "skill_name": "n"})
        assert fallback["skill_name"] == "n"
        assert fallback["description"] == ""
        assert fallback["tags"] == []
        assert fallback["skill_body"] == ""

    def test_tokenize(self):
        assert SkillRetrievalService._tokenize("parse the CSV data") == ["parse", "csv", "data"]
        assert SkillRetrievalService._tokenize("a an the") == []

    def test_get_skill_retrieval_service_singleton(self, monkeypatch):
        monkeypatch.setattr("core.skill_retrieval_service._service", None)
        first = get_skill_retrieval_service()
        assert get_skill_retrieval_service() is first

    def _session_like(self, all_results):
        sess = Session.__new__(Session)
        query = MagicMock()
        query.return_value.filter.return_value.all.side_effect = all_results
        sess.query = query
        return sess

    def test_workspace_no_assigned_skills_returns_empty(self):
        sess = self._session_like([[]])
        with patch("core.skill_retrieval_service.is_skill_injection_enabled",
                   return_value=True), \
                patch("core.skill_registry_service.SkillRegistryService") as cls:
            registry = self._registry_mock()
            cls.return_value = registry
            result = SkillRetrievalService().retrieve_top_skills(
                sess, None, "ws1", "process csv data")
        assert result == ""

    def test_workspace_filtered_to_empty_returns_empty(self):
        sess = self._session_like([[("exec-1",)], [("exec-1",)]])
        with patch("core.skill_retrieval_service.is_skill_injection_enabled",
                   return_value=True), \
                patch("core.skill_registry_service.SkillRegistryService") as cls:
            registry = MagicMock()
            registry.list_skills.return_value = [{"skill_id": "other", "skill_name": "basic"}]
            registry.get_skill.return_value = {
                "skill_name": "basic", "description": "d", "tags": [], "skill_body": "",
            }
            cls.return_value = registry
            result = SkillRetrievalService().retrieve_top_skills(
                sess, None, "ws1", "process csv data")
        assert result == ""

    def test_workspace_full_flow(self):
        sess = self._session_like([[("exec-1",)], [("exec-1",)]])
        with patch("core.skill_retrieval_service.is_skill_injection_enabled",
                   return_value=True), \
                patch("core.skill_registry_service.SkillRegistryService") as cls:
            registry = MagicMock()
            registry.list_skills.return_value = [
                {"skill_id": "exec-1", "skill_name": "basic"},
                {"skill_id": "unassigned", "skill_name": "other"},
            ]
            def get_skill(sid):
                if sid == "exec-1":
                    return {"skill_name": "basic", "description": "handles csv data",
                            "tags": [], "skill_body": ""}
                return {"skill_name": "other", "description": "finance", "tags": [], "skill_body": ""}
            registry.get_skill.side_effect = get_skill
            cls.return_value = registry
            result = SkillRetrievalService().retrieve_top_skills(
                sess, None, "ws1", "data csv", limit=3)
        assert "`basic`" in result
        assert "`other`" not in result


# ===========================================================================
# skill_parser.py
# ===========================================================================

class TestSkillParser:
    def _skill_file(self, tmp_path, name="Test Skill", description="Does things",
                    packages=None, node_packages=None, package_manager=None, body="# Test\n\nbody text"):
        front = {"name": name, "description": description}
        if packages is not None:
            front["packages"] = packages
        if node_packages is not None:
            front["node_packages"] = node_packages
        if package_manager is not None:
            front["package_manager"] = package_manager
        lines = ["---", json.dumps(front), "---", body]
        p = tmp_path / "SKILL.md"
        p.write_text("\n".join(lines))
        return p

    def test_parse_skill_file_happy(self, tmp_path):
        p = self._skill_file(tmp_path, packages=["numpy==1.21.0"], node_packages=["lodash@4.17.21"])
        metadata, body = SkillParser().parse_skill_file(str(p))
        assert metadata["name"] == "Test Skill"
        assert metadata["packages"] == ["numpy==1.21.0"]
        assert metadata["node_packages"] == ["lodash@4.17.21"]
        assert metadata["package_manager"] == "npm"
        assert metadata["skill_type"] == "prompt_only"
        assert "body text" in body

    def test_parse_skill_file_not_found(self, tmp_path):
        metadata, body = SkillParser().parse_skill_file(str(tmp_path / "ghost.md"))
        assert metadata["name"] == "Unnamed Skill"
        assert body == ""

    def test_parse_skill_file_generic_error(self, tmp_path):
        p = self._skill_file(tmp_path)
        with patch("core.skill_parser.frontmatter.loads", side_effect=RuntimeError("yaml boom")):
            metadata, body = SkillParser().parse_skill_file(str(p))
        assert metadata["name"] == "Unnamed Skill"

    def test_parse_skill_file_missing_name_and_description(self, tmp_path):
        p = tmp_path / "SKILL.md"
        p.write_text("---\npackages: []\n---\n# Heading here\n\ncontent")
        metadata, _ = SkillParser().parse_skill_file(str(p))
        assert metadata["name"] == "Unnamed Skill"
        assert metadata["description"] == "Heading here"

    def test_parse_skill_file_empty_body(self, tmp_path):
        p = tmp_path / "SKILL.md"
        p.write_text("---\n---\n")
        metadata, _ = SkillParser().parse_skill_file(str(p))
        assert metadata["name"] == "Unnamed Skill"
        assert metadata["description"] == "No description available"

    def test_parse_skill_file_python_type(self, tmp_path):
        p = self._skill_file(tmp_path, body="```python\nprint(1)\n```")
        metadata, _ = SkillParser().parse_skill_file(str(p))
        assert metadata["skill_type"] == "python_code"

    def test_auto_fix_no_changes(self):
        metadata = {"name": "n", "description": "d"}
        result = SkillParser()._auto_fix_metadata(metadata, "body", "f.md")
        assert result == metadata

    def test_extract_packages_non_list(self):
        result = SkillParser()._extract_packages({"packages": "numpy"}, "f.md")
        assert result == []

    def test_extract_packages_invalid_requirement(self):
        result = SkillParser()._extract_packages({"packages": ["numpy==1.21.0", "not-valid!!"]}, "f.md")
        assert result == ["numpy==1.21.0"]

    def test_extract_node_packages_non_list(self):
        result = SkillParser()._extract_node_packages({"node_packages": "lodash"}, "f.md")
        assert result == []

    def test_extract_node_packages_invalid(self):
        result = SkillParser()._extract_node_packages(
            {"node_packages": ["lodash@4.17.21", "bad spec!"]}, "f.md")
        assert result == ["lodash@4.17.21"]

    def test_validate_npm_package_format(self):
        validate = SkillParser()._validate_npm_package_format
        assert validate("lodash@4.17.21")
        assert validate("express@^4.18.0")
        assert validate("@babel/core@7.0.0")
        assert validate("@scope/name")
        assert validate("axios")
        assert not validate(None)
        assert not validate(123)
        assert not validate("")
        assert not validate("   ")
        assert not validate("@scope")
        assert not validate("bad name!")
        assert not validate("pkg@^1.0.0 with space")

    def test_extract_package_manager_valid(self):
        for pm in ["npm", "yarn", "pnpm"]:
            assert SkillParser()._extract_package_manager({"package_manager": pm}, "f.md") == pm

    def test_extract_package_manager_default(self):
        assert SkillParser()._extract_package_manager({}, "f.md") == "npm"

    def test_extract_package_manager_invalid(self):
        assert SkillParser()._extract_package_manager({"package_manager": "bun"}, "f.md") == "npm"

    def test_detect_skill_type_python_fence(self):
        assert SkillParser()._detect_skill_type({}, "```python\nx\n```") == "python_code"

    def test_detect_skill_type_metadata(self):
        assert SkillParser()._detect_skill_type({"type": "python"}, "text") == "python_code"
        assert SkillParser()._detect_skill_type({"language": "python"}, "text") == "python_code"

    def test_detect_skill_type_default(self):
        assert SkillParser()._detect_skill_type({}, "plain text") == "prompt_only"

    def test_extract_python_code(self):
        body = "intro\n```python\nprint('a')\nprint('b')\n```\noutro\n``` Python\nx = 1\n```\n"
        blocks = SkillParser().extract_python_code(body)
        assert blocks == ["print('a')\nprint('b')", "x = 1"]

    def test_extract_python_code_unclosed(self):
        body = "```python\nprint('never closed')\n"
        blocks = SkillParser().extract_python_code(body)
        assert blocks == ["print('never closed')\n"]

    def test_extract_python_code_no_blocks(self):
        assert SkillParser().extract_python_code("no fences here") == []

    def test_extract_function_signatures(self):
        code = "def add(a, b):\n    \"\"\"Add two numbers.\"\"\"\n    return a + b\n\ndef noop():\n    pass\n"
        functions = SkillParser().extract_function_signatures(code)
        assert functions[0] == {"name": "add", "args": ["a", "b"], "docstring": "Add two numbers."}
        assert functions[1] == {"name": "noop", "args": [], "docstring": ""}

    def test_extract_function_signatures_syntax_error(self):
        assert SkillParser().extract_function_signatures("def broken(") == []

    def test_parse_batch(self, tmp_path):
        p1 = self._skill_file(tmp_path, name="One")
        p2 = tmp_path / "SKILL2.md"
        p2.write_text("---\nname: Two\n---\nbody2")
        result = SkillParser().parse_batch([str(p1), str(p2)])
        assert result["success_count"] == 2
        assert result["failure_count"] == 0
        assert len(result["skills"]) == 2

    def test_parse_batch_with_failure(self, tmp_path):
        parser = SkillParser()
        p = self._skill_file(tmp_path)
        with patch.object(parser, "parse_skill_file", side_effect=ValueError("broken")):
            result = parser.parse_batch([str(p)])
        assert result["success_count"] == 0
        assert result["failure_count"] == 1
        assert "broken" in result["errors"][0]


# ===========================================================================
# supervised_queue_service.py
# ===========================================================================

class _FakeQuery:
    def __init__(self, rows, conditions=None):
        self._rows = list(rows)
        self._conditions = list(conditions or [])

    def filter(self, *conditions, **kwargs):
        return _FakeQuery(self._rows, self._conditions + list(conditions))

    def order_by(self, *a, **k):
        return self

    def limit(self, n):
        return self

    @staticmethod
    def _unwrap(x):
        return x.value if hasattr(x, "value") else x

    def _matches(self, row):
        from sqlalchemy.sql import operators as sa_ops
        for cond in self._conditions:
            left = getattr(cond, "left", None)
            name = getattr(left, "key", None)
            if name is None:
                continue
            actual = getattr(row, name, None)
            op = getattr(cond, "operator", None)
            if op is sa_ops.eq:
                if actual != self._unwrap(getattr(cond, "right", None)):
                    return False
            elif op is sa_ops.in_op:
                right = getattr(cond, "right", None)
                clauses = getattr(right, "clauses", None)
                if clauses:
                    values = [self._unwrap(c) for c in clauses]
                else:
                    values = self._unwrap(right)
                    if not isinstance(values, (list, tuple, set)):
                        values = [values]
                if actual not in values:
                    return False
        return True

    def all(self):
        return [r for r in self._rows if self._matches(r)]

    def first(self):
        for r in self._rows:
            if self._matches(r):
                return r
        return None

    def count(self):
        return len(self.all())


class _FakeDB:
    def __init__(self, tables=None):
        self._tables = tables or {}
        self.added = []
        self.commits = 0
        self.refreshed = []

    def query(self, model):
        return _FakeQuery(self._tables.get(model, []))

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.commits += 1

    def refresh(self, obj):
        self.refreshed.append(obj)


def _queue_entry(**kw):
    base = {
        "id": "q1", "tenant_id": "t1", "agent_id": "a1", "user_id": "u1",
        "trigger_type": "automated", "execution_context": {"key": "value"},
        "status": QueueStatus.pending, "priority": 0, "attempts": 0,
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        "execution_result": None, "last_error": None,
    }
    base.update(kw)
    return SimpleNamespace(**base)


class TestSupervisedQueueService:
    def test_enqueue_execution_default_expiry(self):
        db = _FakeDB({User: [SimpleNamespace(id="u1", tenant_id="t9")]})
        service = SupervisedQueueService(db)
        entry = _run(service.enqueue_execution("a1", "u1", "manual", {"k": 1}))
        assert entry.id.startswith("queue_")
        assert entry.tenant_id == "t9"
        assert entry.status == QueueStatus.pending
        assert entry.attempts == 0
        assert entry.expires_at > datetime.now(timezone.utc) + timedelta(hours=23)
        assert len(db.added) == 1 and db.commits >= 1 and len(db.refreshed) == 1

    def test_enqueue_execution_custom_expiry(self):
        custom = datetime.now(timezone.utc) + timedelta(hours=2)
        db = _FakeDB({User: []})
        service = SupervisedQueueService(db)
        entry = _run(service.enqueue_execution(
            "a1", "u1", "manual", {"k": 1}, priority=5, expires_at=custom,
            supervisor_type="autonomous_agent"))
        assert entry.tenant_id == "default"
        assert entry.priority == 5
        assert entry.expires_at == custom

    def test_enqueue_execution_owner_without_tenant(self):
        db = _FakeDB({User: [SimpleNamespace(id="u1", tenant_id=None)]})
        service = SupervisedQueueService(db)
        entry = _run(service.enqueue_execution("a1", "u1", "manual", {}))
        assert entry.tenant_id == "default"

    def test_process_pending_no_available_users(self):
        db = _FakeDB({UserActivity: []})
        service = SupervisedQueueService(db)
        assert _run(service.process_pending_queues()) == []

    def test_process_pending_skips_unavailable(self):
        db = _FakeDB({
            UserActivity: [SimpleNamespace(user_id="u1", state=UserState.online)],
            SupervisedExecutionQueue: [
                _queue_entry(id="q1", user_id="u1"),
                _queue_entry(id="q2", user_id="u2"),
            ],
        })
        service = SupervisedQueueService(db)
        with patch.object(service, "_get_available_user_ids", return_value=["u1", "u2"]), \
                patch.object(service, "_process_single_queue",
                             new=AsyncMock(return_value=_queue_entry(id="q1"))):
            processed = _run(service.process_pending_queues())
        assert [e.id for e in processed] == ["q1"]

    def test_process_pending_mixed_availability(self):
        db = _FakeDB({
            UserActivity: [SimpleNamespace(user_id="u1", state=UserState.online)],
            SupervisedExecutionQueue: [_queue_entry(id="q1"), _queue_entry(id="q2")],
        })
        service = SupervisedQueueService(db)
        with patch.object(service, "_is_user_available",
                          new=AsyncMock(side_effect=[False, True])), \
                patch.object(service, "_process_single_queue",
                             new=AsyncMock(return_value=_queue_entry(id="q2"))):
            processed = _run(service.process_pending_queues())
        assert [e.id for e in processed] == ["q2"]

    def test_process_pending_success_path(self):
        db = _FakeDB({
            UserActivity: [SimpleNamespace(user_id="u1", state=UserState.online)],
            SupervisedExecutionQueue: [_queue_entry(id="q1")],
        })
        service = SupervisedQueueService(db)
        with patch.object(service, "_is_user_available",
                          new=AsyncMock(return_value=True)), \
                patch.object(service, "_process_single_queue",
                             new=AsyncMock(return_value=_queue_entry(id="q1"))):
            processed = _run(service.process_pending_queues(limit=5))
        assert len(processed) == 1

    def test_process_pending_exception(self):
        service = SupervisedQueueService(_FakeDB())
        with patch.object(service, "_get_available_user_ids",
                          side_effect=RuntimeError("db down")):
            assert _run(service.process_pending_queues()) == []

    def test_cancel_queue_entry_not_found(self):
        service = SupervisedQueueService(_FakeDB({SupervisedExecutionQueue: []}))
        assert _run(service.cancel_queue_entry("q1", "u1")) is False

    def test_cancel_queue_entry_unauthorized(self):
        db = _FakeDB({SupervisedExecutionQueue: [_queue_entry(id="q1", user_id="other")]})
        service = SupervisedQueueService(db)
        assert _run(service.cancel_queue_entry("q1", "u1")) is False

    def test_cancel_queue_entry_not_pending(self):
        db = _FakeDB({
            SupervisedExecutionQueue: [_queue_entry(id="q1", status=QueueStatus.completed)],
        })
        service = SupervisedQueueService(db)
        assert _run(service.cancel_queue_entry("q1", "u1")) is False

    def test_cancel_queue_entry_success(self):
        db = _FakeDB({SupervisedExecutionQueue: [_queue_entry(id="q1")]})
        service = SupervisedQueueService(db)
        with patch.object(service, "update_queue_status", new=AsyncMock()) as upd:
            assert _run(service.cancel_queue_entry("q1", "u1")) is True
        upd.assert_awaited_once_with("q1", QueueStatus.cancelled)

    def test_get_user_queue(self):
        db = _FakeDB({SupervisedExecutionQueue: [_queue_entry(id="q1"), _queue_entry(id="q2")]})
        service = SupervisedQueueService(db)
        assert len(_run(service.get_user_queue("u1"))) == 2
        assert len(_run(service.get_user_queue("u1", QueueStatus.pending))) == 2

    def test_update_queue_status_not_found(self):
        service = SupervisedQueueService(_FakeDB({SupervisedExecutionQueue: []}))
        with pytest.raises(ValueError, match="Queue entry not found"):
            _run(service.update_queue_status("nope", QueueStatus.failed))

    def test_update_queue_status_with_details(self):
        db = _FakeDB({SupervisedExecutionQueue: [_queue_entry(id="q1")]})
        service = SupervisedQueueService(db)
        entry = _run(service.update_queue_status(
            "q1", QueueStatus.completed, execution_id="exec-1", error_message="msg"))
        assert entry.status == QueueStatus.completed
        assert entry.execution_result == {"execution_id": "exec-1"}
        assert entry.last_error == "msg"

    def test_update_queue_status_bare(self):
        db = _FakeDB({SupervisedExecutionQueue: [_queue_entry(id="q1")]})
        service = SupervisedQueueService(db)
        entry = _run(service.update_queue_status("q1", QueueStatus.executing))
        assert entry.status == QueueStatus.executing
        assert entry.execution_result is None
        assert entry.last_error is None

    def test_mark_expired_queues_none(self):
        service = SupervisedQueueService(_FakeDB({SupervisedExecutionQueue: []}))
        assert _run(service.mark_expired_queues()) == 0

    def test_mark_expired_queues_some(self):
        db = _FakeDB({SupervisedExecutionQueue: [
            _queue_entry(id="q1"), _queue_entry(id="q2"), _queue_entry(id="q3"),
        ]})
        service = SupervisedQueueService(db)
        assert _run(service.mark_expired_queues()) == 3
        assert db.commits >= 1

    def test_get_queue_stats(self):
        rows = [
            _queue_entry(id="q1", status=QueueStatus.pending),
            _queue_entry(id="q2", status=QueueStatus.pending),
            _queue_entry(id="q3", status=QueueStatus.failed),
        ]
        service = SupervisedQueueService(_FakeDB({SupervisedExecutionQueue: rows}))
        stats = _run(service.get_queue_stats())
        assert stats["pending"] == 2
        assert stats["failed"] == 1
        assert stats["total"] == 3
        assert stats["executing"] == 0 and stats["completed"] == 0 and stats["cancelled"] == 0

    def test_get_queue_stats_with_user(self):
        rows = [_queue_entry(id="q1", status=QueueStatus.pending)]
        service = SupervisedQueueService(_FakeDB({SupervisedExecutionQueue: rows}))
        stats = _run(service.get_queue_stats(user_id="u1"))
        assert stats["pending"] == 1
        assert stats["total"] == 1

    def test_get_available_user_ids(self):
        rows = [
            SimpleNamespace(user_id="u1", state=UserState.online),
            SimpleNamespace(user_id="u2", state=UserState.away),
            SimpleNamespace(user_id="u3", state=UserState.offline),
        ]
        service = SupervisedQueueService(_FakeDB({UserActivity: rows}))
        assert service._get_available_user_ids() == ["u1", "u2"]

    def test_is_user_available_no_activity(self):
        service = SupervisedQueueService(_FakeDB({UserActivity: []}))
        assert _run(service._is_user_available("u1")) is False

    def test_is_user_available_online(self):
        db = _FakeDB({UserActivity: [SimpleNamespace(user_id="u1", state=UserState.online)]})
        service = SupervisedQueueService(db)
        assert _run(service._is_user_available("u1")) is True

    def test_is_user_available_offline(self):
        db = _FakeDB({UserActivity: [SimpleNamespace(user_id="u1", state=UserState.offline)]})
        service = SupervisedQueueService(db)
        assert _run(service._is_user_available("u1")) is False

    def test_process_single_queue_success(self):
        db = _FakeDB()
        service = SupervisedQueueService(db)
        entry = _queue_entry()
        with patch.object(service, "_create_execution_from_queue",
                          new=AsyncMock(return_value=SimpleNamespace(id="exec-1"))):
            result = _run(service._process_single_queue(entry))
        assert result is entry
        assert entry.status == QueueStatus.completed
        assert entry.execution_result == {"execution_id": "exec-1"}
        assert entry.attempts == 1

    def test_process_single_queue_retry(self):
        db = _FakeDB()
        service = SupervisedQueueService(db)
        entry = _queue_entry()
        with patch.object(service, "_create_execution_from_queue",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = _run(service._process_single_queue(entry))
        assert result is entry
        assert entry.status == QueueStatus.pending
        assert "Attempt 1 failed" in entry.last_error

    def test_process_single_queue_fail_after_max_attempts(self):
        db = _FakeDB()
        service = SupervisedQueueService(db)
        entry = _queue_entry(attempts=3)
        with patch.object(service, "_create_execution_from_queue",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = _run(service._process_single_queue(entry))
        assert result is entry
        assert entry.status == QueueStatus.failed
        assert "Failed after 4 attempts" in entry.last_error

    def test_create_execution_from_queue_agent_missing(self):
        service = SupervisedQueueService(_FakeDB({AgentRegistry: []}))
        with pytest.raises(ValueError, match="Agent not found"):
            _run(service._create_execution_from_queue(_queue_entry()))

    def test_create_execution_from_queue_success(self):
        db = _FakeDB({AgentRegistry: [SimpleNamespace(id="a1", name="My Agent")]})
        service = SupervisedQueueService(db)
        execution = _run(service._create_execution_from_queue(_queue_entry()))
        assert isinstance(execution, AgentExecution)
        assert execution.agent_id == "a1"
        assert execution.tenant_id == "t1"
        assert execution.triggered_by == "queue"
        assert execution.status == "completed"
        assert "q1" in execution.output_summary
        assert json.loads(execution.input_summary) == {"key": "value"}
