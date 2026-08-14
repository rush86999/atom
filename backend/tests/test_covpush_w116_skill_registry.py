"""Backend depth wave 116 (2026-08-13) — coverage push for
core/skill_registry_service.py (95% -> 100%).

Covers the last uncovered branches: lazy HazardSandbox init, agent-capability
None fallback, npm permission denial in the python-with-packages path,
vulnerability warnings (python + node), npm install failure, missing node
code, suspicious (non-malicious) npm scripts, frontmatter parse failure, and
dynamic-reload exception handling. Fully mocked — zero LLM spend.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import frontmatter
import pytest

from core.skill_registry_service import SkillRegistryService

LOW_RISK = {"safe": True, "risk_level": "LOW", "findings": []}

PROMPT_SKILL = """---
name: Greeter
description: Says hello
---
This is a prompt-only skill body.
"""

PY_SKILL = """---
name: Calc
packages:
  - numpy==1.26.0
---
```python
import numpy
print(numpy.__version__)
```
"""

PY_SKILL_NO_PKGS = """---
name: PlainCalc
---
```python
print("hi")
```
"""

BOTH_SKILL = """---
name: BothSkill
packages:
  - numpy==1.26.0
node_packages:
  - lodash@4.17.21
---
```python
x = 1
```
"""

NODE_SKILL = """---
name: NodeSkill
node_packages:
  - lodash@4.17.21
---
```python
x = 1
```
```javascript
console.log("hi")
```
"""


def _make_service(db_session):
    svc = SkillRegistryService(db_session)
    svc._scanner.scan_skill = AsyncMock(return_value=LOW_RISK)
    return svc


async def _import(svc, content):
    return await svc.import_skill("raw_content", content)


def _gov_allows():
    gov = MagicMock()
    gov.check_package_permission.return_value = {"allowed": True, "reason": "ok"}
    return gov


def _patch_audit(monkeypatch):
    monkeypatch.setattr(
        "core.audit_service.audit_service",
        SimpleNamespace(create_package_audit=lambda **kw: None),
    )


class TestSandboxLazyInit:
    """Cover _get_sandbox() lazy init (line 90)."""

    def test_sandbox_created_on_first_use(self, db_session, monkeypatch):
        import core.skill_registry_service as mod

        svc = _make_service(db_session)
        assert svc._sandbox is None
        fake_sandbox = MagicMock()
        monkeypatch.setattr(mod, "HazardSandbox", lambda: fake_sandbox)
        sandbox = svc._get_sandbox()
        assert sandbox is fake_sandbox
        assert svc._sandbox is fake_sandbox
        assert svc._get_sandbox() is fake_sandbox  # cached


class TestExecuteAgentCaps:
    """Cover missing agent capabilities fallback (line 355)."""

    @pytest.mark.asyncio
    async def test_agent_caps_none_executes_as_system(self, db_session, monkeypatch):
        from core.skill_registry_service import create_community_tool

        svc = _make_service(db_session)
        res = await _import(svc, PROMPT_SKILL)
        svc._governance.get_agent_capabilities = MagicMock(return_value=None)

        class FakeTool:
            def _run(self, query):
                return "ok"

        monkeypatch.setattr(
            "core.skill_registry_service.create_community_tool", lambda parsed: FakeTool()
        )
        out = await svc.execute_skill(res["skill_id"], {}, agent_id="ghost-agent")
        assert out["success"] is True
        svc._governance.get_agent_capabilities.assert_called_once_with("ghost-agent")


class TestExecuteNpmPermissionInPythonPath:
    """Cover npm permission denial inside python-with-packages path (429-438)."""

    @pytest.mark.asyncio
    async def test_npm_package_denied_in_python_skill(self, db_session, monkeypatch):
        svc = _make_service(db_session)
        res = await _import(svc, BOTH_SKILL)

        def side_effect(agent_id, package_name, version, package_type=None, db=None):
            if package_name == "lodash":
                return {"allowed": False, "reason": "denylisted"}
            return {"allowed": True, "reason": "ok"}

        gov = MagicMock()
        gov.check_package_permission.side_effect = side_effect
        monkeypatch.setattr(
            "core.package_governance_service.PackageGovernanceService", lambda: gov
        )
        with pytest.raises(ValueError, match="npm package permission denied"):
            await svc.execute_skill(res["skill_id"], {}, agent_id="system")

    @pytest.mark.asyncio
    async def test_npm_permission_check_error_re_raises(self, db_session, monkeypatch):
        svc = _make_service(db_session)
        res = await _import(svc, BOTH_SKILL)

        def side_effect(agent_id, package_name, version, package_type=None, db=None):
            if package_name == "lodash":
                raise ValueError("inner governance failure")
            return {"allowed": True, "reason": "ok"}

        gov = MagicMock()
        gov.check_package_permission.side_effect = side_effect
        monkeypatch.setattr(
            "core.package_governance_service.PackageGovernanceService", lambda: gov
        )
        with pytest.raises(ValueError, match="inner governance failure"):
            await svc.execute_skill(res["skill_id"], {}, agent_id="system")


class TestPythonVulnerabilityWarning:
    """Cover python package vulnerabilities log (line 653)."""

    @pytest.mark.asyncio
    async def test_python_install_with_vulnerabilities_proceeds(
        self, db_session, monkeypatch
    ):
        svc = _make_service(db_session)
        res = await _import(svc, PY_SKILL)
        pkg_installer = MagicMock()
        pkg_installer.install_packages.return_value = {
            "success": True,
            "image_tag": "img-1",
            "vulnerabilities": [{"id": "CVE-2026-0001"}],
        }
        pkg_installer.execute_with_packages.return_value = "pkg output"
        monkeypatch.setattr("core.package_installer.PackageInstaller", lambda: pkg_installer)
        monkeypatch.setattr(
            "core.package_governance_service.PackageGovernanceService", lambda: _gov_allows()
        )
        out = await svc.execute_skill(res["skill_id"], {}, agent_id="system")
        assert out["success"] is True and out["result"] == "pkg output"


class TestNodeEdgeBranches:
    """Cover nodejs install failure / vulnerabilities / missing code (737-754)."""

    @pytest.mark.asyncio
    async def test_nodejs_install_failure(self, db_session, monkeypatch):
        import core.npm_script_analyzer as nsa

        svc = _make_service(db_session)
        res = await _import(svc, NODE_SKILL)
        monkeypatch.setattr(
            "core.package_governance_service.PackageGovernanceService", lambda: _gov_allows()
        )
        _patch_audit(monkeypatch)
        npm_installer = MagicMock()
        npm_installer.install_packages.return_value = {
            "success": False,
            "error": "registry timeout",
        }
        monkeypatch.setattr("core.npm_package_installer.NpmPackageInstaller", lambda: npm_installer)
        monkeypatch.setattr(
            nsa.NpmScriptAnalyzer,
            "analyze_package_scripts",
            lambda self, packages: {"malicious": False, "warnings": [], "details": [], "scripts_found": []},
        )
        out = await svc.execute_skill(res["skill_id"], {}, agent_id="system")
        assert out["success"] is False and "registry timeout" in out["error"]

    @pytest.mark.asyncio
    async def test_nodejs_executor_install_failure_defensive_branch(
        self, db_session, monkeypatch
    ):
        """Cover the defensive raise in _execute_nodejs_skill_with_packages
        (737-741): reachable only when _install_npm_dependencies_for_skill is
        overridden to return failure without raising."""
        svc = _make_service(db_session)
        res = await _import(svc, NODE_SKILL)
        svc._install_npm_dependencies_for_skill = MagicMock(
            return_value={"success": False, "error": "registry timeout"}
        )
        with pytest.raises(ValueError, match="npm installation failed: registry timeout"):
            await svc._execute_nodejs_skill_with_packages(
                {
                    "skill_name": "NodeSkill",
                    "skill_id": res["skill_id"],
                    "skill_body": "x",
                },
                {},
                ["lodash@4.17.21"],
                "npm",
                "system",
            )

    @pytest.mark.asyncio
    async def test_nodejs_vulnerabilities_warn_and_proceed(self, db_session, monkeypatch):
        import core.npm_script_analyzer as nsa

        svc = _make_service(db_session)
        res = await _import(svc, NODE_SKILL)
        monkeypatch.setattr(
            "core.package_governance_service.PackageGovernanceService", lambda: _gov_allows()
        )
        _patch_audit(monkeypatch)
        npm_installer = MagicMock()
        npm_installer.install_packages.return_value = {
            "success": True,
            "image_tag": "npm-img",
            "vulnerabilities": [{"id": "CVE-2026-9999"}],
        }
        npm_installer.execute_with_packages.return_value = "node output"
        monkeypatch.setattr("core.npm_package_installer.NpmPackageInstaller", lambda: npm_installer)
        monkeypatch.setattr(
            nsa.NpmScriptAnalyzer,
            "analyze_package_scripts",
            lambda self, packages: {"malicious": False, "warnings": [], "details": [], "scripts_found": []},
        )
        out = await svc.execute_skill(res["skill_id"], {}, agent_id="system")
        assert out["success"] is True and out["result"] == "node output"

    @pytest.mark.asyncio
    async def test_nodejs_missing_code_raises(self, db_session, monkeypatch):
        import core.npm_script_analyzer as nsa

        from core.models import SkillExecution

        svc = _make_service(db_session)
        res = await _import(svc, NODE_SKILL)
        exec_row = db_session.query(SkillExecution).filter(SkillExecution.id == res["skill_id"]).first()
        exec_row.input_params = {**exec_row.input_params, "skill_body": ""}
        db_session.commit()
        monkeypatch.setattr(
            "core.package_governance_service.PackageGovernanceService", lambda: _gov_allows()
        )
        _patch_audit(monkeypatch)
        npm_installer = MagicMock()
        npm_installer.install_packages.return_value = {
            "success": True,
            "image_tag": "npm-img",
            "vulnerabilities": [],
        }
        monkeypatch.setattr("core.npm_package_installer.NpmPackageInstaller", lambda: npm_installer)
        monkeypatch.setattr(
            nsa.NpmScriptAnalyzer,
            "analyze_package_scripts",
            lambda self, packages: {"malicious": False, "warnings": [], "details": [], "scripts_found": []},
        )
        out = await svc.execute_skill(res["skill_id"], {}, agent_id="system")
        assert out["success"] is False
        assert "No Node.js code found" in out["error"]


class TestSuspiciousNpmScripts:
    """Cover non-malicious script warnings (line 902)."""

    @pytest.mark.asyncio
    async def test_suspicious_scripts_warn_and_proceed(self, db_session, monkeypatch):
        import core.npm_script_analyzer as nsa

        svc = _make_service(db_session)
        res = await _import(svc, NODE_SKILL)
        monkeypatch.setattr(
            "core.package_governance_service.PackageGovernanceService", lambda: _gov_allows()
        )
        _patch_audit(monkeypatch)
        npm_installer = MagicMock()
        npm_installer.install_packages.return_value = {
            "success": True,
            "image_tag": "npm-img",
            "vulnerabilities": [],
        }
        npm_installer.execute_with_packages.return_value = "node output"
        monkeypatch.setattr("core.npm_package_installer.NpmPackageInstaller", lambda: npm_installer)
        monkeypatch.setattr(
            nsa.NpmScriptAnalyzer,
            "analyze_package_scripts",
            lambda self, packages: {
                "malicious": False,
                "warnings": ["postinstall uses curl"],
                "details": [],
                "scripts_found": ["postinstall"],
            },
        )
        out = await svc.execute_skill(res["skill_id"], {}, agent_id="system")
        assert out["success"] is True and out["result"] == "node output"


class TestDetectSkillTypeFallback:
    """Cover frontmatter parse failure in type detection (lines 1025-1026)."""

    def test_frontmatter_parse_error_falls_back_to_python(self, db_session, monkeypatch):
        svc = _make_service(db_session)

        def broken_loads(content):
            raise ValueError("bad frontmatter")

        monkeypatch.setattr(frontmatter, "loads", broken_loads)
        assert svc.detect_skill_type("no frontmatter here") == "python"

    def test_frontmatter_parse_error_no_hint(self, db_session, monkeypatch):
        svc = _make_service(db_session)

        def broken_loads(content):
            raise RuntimeError("boom")

        monkeypatch.setattr(frontmatter, "loads", broken_loads)
        assert svc.detect_skill_type("plain text") == "python"


class TestReloadDynamicallyError:
    """Cover reload_skill_dynamically exception path (lines 1186-1188)."""

    def test_reload_exception_returns_error(self, db_session, monkeypatch):
        def broken_loader():
            raise RuntimeError("loader exploded")

        monkeypatch.setattr("core.skill_dynamic_loader.get_global_loader", broken_loader)
        svc = _make_service(db_session)
        result = svc.reload_skill_dynamically(f"skill-{uuid.uuid4().hex[:8]}")
        assert result["success"] is False
        assert "loader exploded" in result["error"]

    def test_reload_not_loaded_returns_error(self, db_session, monkeypatch):
        loader = MagicMock()
        loader.reload_skill.return_value = None
        monkeypatch.setattr("core.skill_dynamic_loader.get_global_loader", lambda: loader)
        svc = _make_service(db_session)
        result = svc.reload_skill_dynamically("skill-x")
        assert result["success"] is False
        assert "not loaded" in result["error"]
