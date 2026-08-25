"""Coverage-push + bug-hunt: core/skill_registry_service.py.

TDD: failing tests first for every bug, then minimal fixes.
Bugs hunted here:
  * execute_skill creates its SkillExecution record without tenant_id
    (nullable=False) → IntegrityError on EVERY community-skill execution.
  * execute_skill swallows non-ValueError exceptions from the package
    permission check → supply-chain governance fail-open (execution proceeds
    with an unvetted package).
  * _install_npm_dependencies_for_skill calls analyze_package_scripts with two
    args while the analyzer takes one → TypeError on every Node.js execution.

Docker/npm/audit/scan layers are mocked; no real network or containers.
"""
from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.models import EpisodeSegment, SkillExecution

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
    from core.skill_registry_service import SkillRegistryService
    svc = SkillRegistryService(db_session)
    svc._scanner.scan_skill = AsyncMock(return_value=LOW_RISK)
    return svc


async def _import(svc, content, metadata=None):
    return await svc.import_skill("raw_content", content, metadata)


# ===========================================================================
# import_skill — full lifecycle
# ===========================================================================
class TestImportSkillAsync:
    @pytest.mark.asyncio
    async def test_import_active_for_low_risk(self, db_session):
        svc = _make_service(db_session)
        res = await _import(svc, PROMPT_SKILL, {"author": "me"})
        assert res["status"] == "Active" and res["skill_name"] == "Greeter"
        assert res["metadata"]["author"] == "me"
        assert res["metadata"]["packages"] == [] and res["metadata"]["node_packages"] == []
        row = db_session.query(SkillExecution).filter(SkillExecution.id == res["skill_id"]).first()
        assert row.skill_source == "community" and row.status == "Active"
        assert row.sandbox_enabled is False

    @pytest.mark.asyncio
    async def test_import_untrusted_for_high_risk(self, db_session):
        svc = _make_service(db_session)
        svc._scanner.scan_skill = AsyncMock(return_value={"safe": False, "risk_level": "CRITICAL", "findings": ["os.system"]})
        res = await _import(svc, PY_SKILL)
        assert res["status"] == "Untrusted"
        row = db_session.query(SkillExecution).filter(SkillExecution.id == res["skill_id"]).first()
        assert row.status == "Untrusted" and row.sandbox_enabled is True
        assert row.security_scan_result["risk_level"] == "CRITICAL"

    @pytest.mark.asyncio
    async def test_import_extracts_packages_and_manager(self, db_session):
        svc = _make_service(db_session)
        res = await _import(svc, PY_SKILL)
        assert res["metadata"]["packages"] == ["numpy==1.26.0"]
        assert res["metadata"]["skill_type"] == "python_code"
        row = db_session.query(SkillExecution).filter(SkillExecution.id == res["skill_id"]).first()
        assert row.input_params["node_packages"] == []
        assert row.input_params["package_manager"] == "npm"

    @pytest.mark.asyncio
    async def test_import_bad_frontmatter_rolls_back(self, db_session):
        svc = _make_service(db_session)
        with pytest.raises(Exception):
            await _import(svc, "---\nnot: [valid\n---\nbody")


# ===========================================================================
# list_skills / get_skill
# ===========================================================================
class TestListAndGet:
    @pytest.mark.asyncio
    async def test_list_filters_status_type_limit(self, db_session):
        svc = _make_service(db_session)
        uid = uuid.uuid4().hex[:6]
        py = PY_SKILL.replace("name: Calc", f"name: Calc-{uid}")
        prompt = PROMPT_SKILL.replace("name: Greeter", f"name: Greeter-{uid}")
        await _import(svc, py)          # python_code / Active
        await _import(svc, prompt)      # prompt_only / Active
        svc._scanner.scan_skill = AsyncMock(return_value={"safe": False, "risk_level": "HIGH", "findings": []})
        await _import(svc, py)          # python_code / Untrusted
        all_skills = svc.list_skills()
        mine = [s for s in all_skills if f"-{uid}" in s["skill_name"]]
        assert len(mine) == 3
        assert any(s["status"] == "Untrusted" for s in mine)
        assert len(svc.list_skills(status="Active")) >= 2
        assert len(svc.list_skills(status="Untrusted")) >= 1
        assert len(svc.list_skills(skill_type="python_code")) >= 2
        assert len(svc.list_skills(limit=2)) == 2
        got = svc.list_skills(skill_type="prompt_only")
        assert any(f"-{uid}" in s["skill_name"] for s in got)

    @pytest.mark.asyncio
    async def test_get_skill_full_and_missing(self, db_session):
        svc = _make_service(db_session)
        res = await _import(svc, PY_SKILL)
        s = svc.get_skill(res["skill_id"])
        assert s["skill_name"] == "Calc"
        assert s["packages"] == ["numpy==1.26.0"]
        assert s["skill_body"].startswith("```python")
        assert s["status"] == "Active" and s["sandbox_enabled"] is True
        assert svc.get_skill("nope") is None


# ===========================================================================
# execute_skill — functional paths (mocked sandbox/installers)
# ===========================================================================
class TestExecuteSkill:
    @pytest.mark.asyncio
    async def test_execute_prompt_skill_succeeds(self, db_session, monkeypatch):
        """BUG (HIGH): execution record lacked tenant_id → IntegrityError on
        every community-skill execution."""
        from core.skill_registry_service import create_community_tool
        svc = _make_service(db_session)
        res = await _import(svc, PROMPT_SKILL)
        seen = {}

        class FakeTool:
            def _run(self, query):
                seen["query"] = query
                return "hello there"

        monkeypatch.setattr("core.skill_registry_service.create_community_tool", lambda parsed: FakeTool())
        out = await svc.execute_skill(res["skill_id"], {"query": "hi"}, agent_id="system")
        assert out["success"] is True
        assert out["result"] == "hello there"
        assert seen["query"] == "hi"
        exec_row = db_session.query(SkillExecution).filter(SkillExecution.id == out["execution_id"]).first()
        assert exec_row.status == "success" and exec_row.output_result["result"] == "hello there"
        seg = db_session.query(EpisodeSegment).filter(EpisodeSegment.id == out["episode_id"]).first()
        assert seg is not None and seg.segment_type == "skill_success"

    @pytest.mark.asyncio
    async def test_execute_unknown_skill_type_fails(self, db_session, monkeypatch):
        from core.skill_registry_service import SkillRegistryService
        from core.skill_registry_service import create_community_tool
        svc = _make_service(db_session)
        res = await _import(svc, PROMPT_SKILL)
        row = db_session.query(SkillExecution).filter(SkillExecution.id == res["skill_id"]).first()
        row.input_params = {**row.input_params, "skill_type": "bogus_type"}
        db_session.commit()
        monkeypatch.setattr("core.skill_registry_service.create_community_tool", lambda parsed: MagicMock())
        out = await svc.execute_skill(res["skill_id"], {}, agent_id="system")
        assert out["success"] is False and "Unknown skill type" in out["error"]
        seg = db_session.query(EpisodeSegment).filter(EpisodeSegment.id == out["episode_id"]).first()
        assert seg.segment_type == "skill_failure"

    @pytest.mark.asyncio
    async def test_execute_missing_skill_raises(self, db_session):
        svc = _make_service(db_session)
        with pytest.raises(ValueError, match="not found"):
            await svc.execute_skill("nope", {})

    @pytest.mark.asyncio
    async def test_student_denied_python_skill(self, db_session):
        svc = _make_service(db_session)
        res = await _import(svc, PY_SKILL_NO_PKGS)
        svc._governance.get_agent_capabilities = MagicMock(
            return_value={"maturity_level": "student", "confidence_score": 0.5},
        )
        with pytest.raises(ValueError, match="STUDENT agents cannot execute Python skills"):
            await svc.execute_skill(res["skill_id"], {}, agent_id="stud-1")

    @pytest.mark.asyncio
    async def test_python_skill_sandbox_execution(self, db_session):
        svc = _make_service(db_session)
        res = await _import(svc, PY_SKILL_NO_PKGS)
        sandbox = MagicMock()
        sandbox.execute_python.return_value = "sandbox output"
        svc._sandbox = sandbox
        out = await svc.execute_skill(res["skill_id"], {"query": "q"}, agent_id="system")
        assert out["success"] is True and out["result"] == "sandbox output"
        assert sandbox.execute_python.call_args[0][0] == 'print("hi")'


class TestExecuteSkillPythonPackages:
    @pytest.mark.asyncio
    async def test_python_with_packages(self, db_session, monkeypatch):
        svc = _make_service(db_session)
        res = await _import(svc, PY_SKILL)
        pkg_installer = MagicMock()
        pkg_installer.install_packages.return_value = {"success": True, "image_tag": "img-1", "vulnerabilities": []}
        pkg_installer.execute_with_packages.return_value = "pkg output"
        monkeypatch.setattr("core.package_installer.PackageInstaller", lambda: pkg_installer)
        gov = MagicMock()
        gov.check_package_permission.return_value = {"allowed": True, "reason": "ok"}
        monkeypatch.setattr("core.package_governance_service.PackageGovernanceService", lambda: gov)
        out = await svc.execute_skill(res["skill_id"], {}, agent_id="system")
        assert out["success"] is True and out["result"] == "pkg output"
        gov.check_package_permission.assert_called_once()
        pkg_installer.install_packages.assert_called_once()

    @pytest.mark.asyncio
    async def test_python_package_permission_denied(self, db_session, monkeypatch):
        svc = _make_service(db_session)
        res = await _import(svc, PY_SKILL)
        gov = MagicMock()
        gov.check_package_permission.return_value = {"allowed": False, "reason": "denylisted"}
        monkeypatch.setattr("core.package_governance_service.PackageGovernanceService", lambda: gov)
        with pytest.raises(ValueError, match="Package permission denied"):
            await svc.execute_skill(res["skill_id"], {}, agent_id="system")

    @pytest.mark.asyncio
    async def test_python_package_install_failure(self, db_session, monkeypatch):
        svc = _make_service(db_session)
        res = await _import(svc, PY_SKILL)
        pkg_installer = MagicMock()
        pkg_installer.install_packages.return_value = {"success": False, "error": "pip exploded"}
        monkeypatch.setattr("core.package_installer.PackageInstaller", lambda: pkg_installer)
        gov = MagicMock()
        gov.check_package_permission.return_value = {"allowed": True, "reason": "ok"}
        monkeypatch.setattr("core.package_governance_service.PackageGovernanceService", lambda: gov)
        out = await svc.execute_skill(res["skill_id"], {}, agent_id="system")
        assert out["success"] is False and "Package installation failed" in out["error"]

    @pytest.mark.asyncio
    async def test_python_package_no_code_in_body(self, db_session, monkeypatch):
        svc = _make_service(db_session)
        res = await _import(svc, PY_SKILL)
        row = db_session.query(SkillExecution).filter(SkillExecution.id == res["skill_id"]).first()
        row.input_params = {**row.input_params, "skill_body": "no code here"}
        db_session.commit()
        pkg_installer = MagicMock()
        pkg_installer.install_packages.return_value = {"success": True, "image_tag": "i", "vulnerabilities": []}
        pkg_installer.execute_with_packages.return_value = "should not run"
        monkeypatch.setattr("core.package_installer.PackageInstaller", lambda: pkg_installer)
        gov = MagicMock()
        gov.check_package_permission.return_value = {"allowed": True, "reason": "ok"}
        monkeypatch.setattr("core.package_governance_service.PackageGovernanceService", lambda: gov)
        out = await svc.execute_skill(res["skill_id"], {}, agent_id="system")
        assert out["success"] is False and "No Python code found" in out["error"]


class TestExecuteSkillGovernanceFailClosed:
    """BUG (HIGH): non-ValueError exceptions from check_package_permission were
    swallowed → the skill executed with an UNVETTED package (fail-open)."""

    @pytest.mark.asyncio
    async def test_python_governance_error_fails_closed(self, db_session, monkeypatch):
        svc = _make_service(db_session)
        res = await _import(svc, PY_SKILL)
        pkg_installer = MagicMock()
        pkg_installer.install_packages.return_value = {"success": True, "image_tag": "i", "vulnerabilities": []}
        monkeypatch.setattr("core.package_installer.PackageInstaller", lambda: pkg_installer)
        gov = MagicMock()
        gov.check_package_permission.side_effect = RuntimeError("governance down")
        monkeypatch.setattr("core.package_governance_service.PackageGovernanceService", lambda: gov)
        with pytest.raises(ValueError, match="permission check failed"):
            await svc.execute_skill(res["skill_id"], {}, agent_id="system")
        pkg_installer.install_packages.assert_not_called()

    @pytest.mark.asyncio
    async def test_npm_governance_error_fails_closed(self, db_session, monkeypatch):
        both = """---
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
        svc = _make_service(db_session)
        res = await _import(svc, both)
        gov = MagicMock()

        def side_effect(agent_id, package_name, version, package_type=None, db=None):
            if package_name == "lodash":
                raise RuntimeError("governance down")
            return {"allowed": True, "reason": "ok"}

        gov.check_package_permission.side_effect = side_effect
        monkeypatch.setattr("core.package_governance_service.PackageGovernanceService", lambda: gov)
        with pytest.raises(ValueError, match="npm package permission check failed"):
            await svc.execute_skill(res["skill_id"], {}, agent_id="system")


class TestExecuteSkillNode:
    @pytest.mark.asyncio
    async def test_nodejs_skill_with_packages(self, db_session, monkeypatch):
        """BUG (MED): analyze_package_scripts(packages, package_manager) called
        with two args while the analyzer takes one → TypeError on every Node.js
        execution."""
        import core.npm_script_analyzer as nsa

        svc = _make_service(db_session)
        res = await _import(svc, NODE_SKILL)
        gov = MagicMock()
        gov.check_package_permission.return_value = {"allowed": True, "reason": "ok"}
        monkeypatch.setattr("core.package_governance_service.PackageGovernanceService", lambda: gov)
        monkeypatch.setattr("core.audit_service.audit_service", SimpleNamespace(create_package_audit=lambda **kw: None))
        npm_installer = MagicMock()
        npm_installer.install_packages.return_value = {"success": True, "image_tag": "npm-img", "vulnerabilities": []}
        npm_installer.execute_with_packages.return_value = "node output"
        monkeypatch.setattr("core.npm_package_installer.NpmPackageInstaller", lambda: npm_installer)
        monkeypatch.setattr(
            nsa.NpmScriptAnalyzer,
            "analyze_package_scripts",
            lambda self, packages: {"malicious": False, "warnings": [], "details": [], "scripts_found": []},
        )
        out = await svc.execute_skill(res["skill_id"], {}, agent_id="system")
        assert out["success"] is True and out["result"] == "node output"
        assert gov.check_package_permission.call_args.kwargs["package_type"] == "npm"
        npm_installer.install_packages.assert_called_once()

    @pytest.mark.asyncio
    async def test_nodejs_malicious_scripts_blocked(self, db_session, monkeypatch):
        import core.npm_script_analyzer as nsa

        svc = _make_service(db_session)
        res = await _import(svc, NODE_SKILL)
        gov = MagicMock()
        gov.check_package_permission.return_value = {"allowed": True, "reason": "ok"}
        monkeypatch.setattr("core.package_governance_service.PackageGovernanceService", lambda: gov)
        monkeypatch.setattr("core.audit_service.audit_service", SimpleNamespace(create_package_audit=lambda **kw: None))
        monkeypatch.setattr(
            nsa.NpmScriptAnalyzer,
            "analyze_package_scripts",
            lambda self, packages: {"malicious": True, "warnings": ["postinstall evil"], "details": [], "scripts_found": []},
        )
        out = await svc.execute_skill(res["skill_id"], {}, agent_id="system")
        assert out["success"] is False and "Malicious postinstall" in out["error"]
    @pytest.mark.asyncio
    async def test_nodejs_npm_permission_denied(self, db_session, monkeypatch):
        svc = _make_service(db_session)
        res = await _import(svc, NODE_SKILL)
        gov = MagicMock()
        gov.check_package_permission.return_value = {"allowed": False, "reason": "denylisted"}
        monkeypatch.setattr("core.package_governance_service.PackageGovernanceService", lambda: gov)
        monkeypatch.setattr("core.audit_service.audit_service", SimpleNamespace(create_package_audit=lambda **kw: None))
        out = await svc.execute_skill(res["skill_id"], {}, agent_id="system")
        assert out["success"] is False and "blocked by governance" in out["error"]

    @pytest.mark.asyncio
    async def test_nodejs_install_failure(self, db_session, monkeypatch):
        import core.npm_script_analyzer as nsa

        svc = _make_service(db_session)
        res = await _import(svc, NODE_SKILL)
        gov = MagicMock()
        gov.check_package_permission.return_value = {"allowed": True, "reason": "ok"}
        monkeypatch.setattr("core.package_governance_service.PackageGovernanceService", lambda: gov)
        monkeypatch.setattr("core.audit_service.audit_service", SimpleNamespace(create_package_audit=lambda **kw: None))
        npm_installer = MagicMock()
        npm_installer.install_packages.return_value = {"success": False, "error": "npm registry down"}
        monkeypatch.setattr("core.npm_package_installer.NpmPackageInstaller", lambda: npm_installer)
        monkeypatch.setattr(
            nsa.NpmScriptAnalyzer,
            "analyze_package_scripts",
            lambda self, packages: {"malicious": False, "warnings": [], "details": [], "scripts_found": []},
        )
        out = await svc.execute_skill(res["skill_id"], {}, agent_id="system")
        assert out["success"] is False and "npm registry down" in out["error"]


# ===========================================================================
# Direct unit coverage — private helpers
# ===========================================================================
class TestExecuteHelpers:
    def test_python_skill_sandbox_required(self, db_session):
        svc = _make_service(db_session)
        with pytest.raises(ValueError, match="requires sandbox"):
            svc._execute_python_skill({"skill_name": "x", "sandbox_enabled": False, "skill_body": "```python\nprint(1)\n```"}, {})
        with pytest.raises(ValueError, match="No Python code found"):
            svc._execute_python_skill({"skill_name": "x", "sandbox_enabled": True, "skill_body": "no code"}, {})

    def test_extract_nodejs_code_variants(self, db_session):
        svc = _make_service(db_session)
        assert svc._extract_nodejs_code("```javascript\nconsole.log(1)\n```\ntrailing") == "console.log(1)"
        assert svc._extract_nodejs_code("```node\nx()\n```") == "x()"
        assert svc._extract_nodejs_code("``` js\ny()\n```") == "y()"
        assert svc._extract_nodejs_code("plain node code") == "plain node code"

    def test_parse_npm_package(self, db_session):
        svc = _make_service(db_session)
        assert svc._parse_npm_package("lodash@4.17.21") == ("lodash", "4.17.21")
        assert svc._parse_npm_package("express") == ("express", "latest")
        assert svc._parse_npm_package("@scope/name@^1.0.0") == ("@scope/name", "^1.0.0")
        assert svc._parse_npm_package("@scope/name") == ("@scope/name", "latest")
        assert svc._parse_npm_package("a@b@c") == ("a", "b@c")

    def test_summarize_inputs(self, db_session):
        svc = _make_service(db_session)
        assert svc._summarize_inputs({}) == "{}"
        out = svc._summarize_inputs({"big": "x" * 150, "ok": 1})
        assert out.startswith("{") and "..." in out and "1" in out

    def test_detect_skill_type(self, db_session):
        svc = _make_service(db_session)
        assert svc.detect_skill_type("---\nnode_packages:\n  - lodash\n---\nbody") == "npm"
        assert svc.detect_skill_type("---\npython_packages:\n  - numpy\n---\nbody") == "python"
        assert svc.detect_skill_type("---\npackages:\n  - numpy\n---\nbody") == "python"
        assert svc.detect_skill_type("Code file: skill.js") == "npm"
        assert svc.detect_skill_type("Code file: skill.py") == "python"
        assert svc.detect_skill_type("```python\nx=1\n```") == "python"
        assert svc.detect_skill_type("plain") == "python"


class TestLifecycle:
    def test_promote_skill(self, db_session):
        svc = _make_service(db_session)
        res = asyncio.run(_import(svc, PROMPT_SKILL))
        out = svc.promote_skill(res["skill_id"])
        assert out["status"] == "Active" and out["message"] == "Skill is already Active"
        with pytest.raises(ValueError, match="Skill not found"):
            svc.promote_skill("missing-1")

    def test_promote_flow(self, db_session):
        svc = _make_service(db_session)
        svc._scanner.scan_skill = AsyncMock(return_value={"safe": False, "risk_level": "HIGH", "findings": []})
        res = asyncio.run(_import(svc, PY_SKILL))
        out = svc.promote_skill(res["skill_id"])
        assert out["status"] == "Active" and out["previous_status"] == "Untrusted"
        row = db_session.query(SkillExecution).filter(SkillExecution.id == res["skill_id"]).first()
        assert row.status == "Active"

    def test_delete_skill(self, db_session):
        svc = _make_service(db_session)
        res = asyncio.run(_import(svc, PROMPT_SKILL))
        out = svc.delete_skill(res["skill_id"])
        assert out["deleted"] is True and out["skill_name"] == "Greeter"
        assert db_session.query(SkillExecution).filter(SkillExecution.id == res["skill_id"]).count() == 0
        with pytest.raises(ValueError, match="Skill not found"):
            svc.delete_skill(res["skill_id"])

    def test_load_and_reload_dynamic(self, db_session, monkeypatch):
        svc = _make_service(db_session)
        loader = MagicMock()
        loader.load_skill.return_value = object()
        loader.reload_skill.return_value = object()
        monkeypatch.setattr("core.skill_dynamic_loader.get_global_loader", lambda: loader)
        out = svc.load_skill_dynamically("s1", "/tmp/s1.py")
        assert out["success"] is True and out["skill_id"] == "s1"
        out = svc.reload_skill_dynamically("s1")
        assert out["success"] is True
        loader.load_skill.return_value = None
        out = svc.load_skill_dynamically("s1", "/tmp/s1.py")
        assert out["success"] is False
        loader.reload_skill.return_value = None
        assert svc.reload_skill_dynamically("s1")["success"] is False

    def test_load_dynamic_error_path(self, db_session, monkeypatch):
        svc = _make_service(db_session)
        monkeypatch.setattr(
            "core.skill_dynamic_loader.get_global_loader",
            lambda: (_ for _ in ()).throw(RuntimeError("no loader")),
        )
        out = svc.load_skill_dynamically("s1", "/tmp/s1.py")
        assert out["success"] is False and "no loader" in out["error"]

    def test_create_execution_episode_failure_returns_none(self, db_session, monkeypatch):
        svc = _make_service(db_session)
        monkeypatch.setattr("core.skill_registry_service.EpisodeSegment", MagicMock())
        seg_id = asyncio.run(
            svc._create_execution_episode("S", "agent-1", {}, "res", None, 1.0)
        )
        assert seg_id is None
