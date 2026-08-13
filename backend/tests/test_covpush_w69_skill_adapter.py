# -*- coding: utf-8 -*-
"""Coverage wave 69 — core/skill_adapter (standalone, fully mocked,
zero LLM spend, no network, no real DB).

- langchain-absent fallback BaseTool stand-in: _run/_arun raise
  NotImplementedError loudly (both subclass adapters override them, so the
  stand-in is exercised via direct dispatch to the base implementation).
- CommunitySkillTool: CLI skill dispatch (_execute_cli_skill success w/ and
  w/o stderr, failure, exception), _parse_cli_args flag matrix
  (port/host/workers/host-mount/dev/foreground/config --show-daemon/none),
  prompt-only interpolation ({{query}}, {query}, append, format failure),
  python skill (sandbox disabled → RuntimeError; sandboxed success; Docker
  daemon not running → SANDBOX_ERROR; other RuntimeError re-raised; generic
  EXECUTION_ERROR), package execution (install success ± vulnerability
  warning, install failure, execute failure), _extract_function_code
  wrapper idempotence, unknown skill type ValueError, _arun delegation.
- create_community_tool factory: explicit fields, defaults, packages passthrough.
- NodeJsSkillAdapter: __init__ wiring, lazy installer/governance properties,
  _parse_npm_package (scoped+version, scoped bare, name@version, bare name),
  install_npm_dependencies (governance-blocked, malicious scripts, benign
  warnings, installer failure, success with db.close), execute_nodejs_code
  success/exception, _run success/install-fail/execution-fail, _arun.
"""
from unittest.mock import ANY, MagicMock, patch

import pytest

import core.skill_adapter as sa
from core.skill_adapter import (
    CommunitySkillInput,
    CommunitySkillTool,
    NodeJsSkillAdapter,
    create_community_tool,
)


# ============================================================================
# langchain-absent fallback BaseTool stand-in
# ============================================================================

class TestFallbackBaseTool:
    def test_base_run_raises_not_implemented(self):
        tool = CommunitySkillTool()
        with pytest.raises(NotImplementedError, match="langchain not installed"):
            sa.BaseTool._run(tool, "x")

    def test_base_arun_raises_not_implemented(self):
        import asyncio
        tool = CommunitySkillTool()
        with pytest.raises(NotImplementedError, match="langchain not installed"):
            asyncio.run(sa.BaseTool._arun(tool, "x"))

    def test_community_skill_input_allows_extra_fields(self):
        inp = CommunitySkillInput(query="q", extra_field=42)
        assert inp.query == "q"
        assert inp.extra_field == 42


# ============================================================================
# CommunitySkillTool — CLI skills
# ============================================================================

class TestCliSkillExecution:
    def _tool(self, skill_id="atom-daemon", query="", content=""):
        return CommunitySkillTool(
            name="daemon",
            description="d",
            skill_id=skill_id,
            skill_type="prompt_only",
            skill_content=content,
        )

    def test_cli_skill_success_no_stderr(self):
        tool = self._tool()
        with patch(
            "core.skill_adapter.execute_atom_cli_command",
            return_value={"success": True, "stdout": "running", "stderr": ""},
        ) as exec_mock:
            result = tool._run("status")
        exec_mock.assert_called_once()
        assert "Command executed successfully" in result
        assert "running" in result

    def test_cli_skill_success_with_stderr(self):
        tool = self._tool()
        with patch(
            "core.skill_adapter.execute_atom_cli_command",
            return_value={"success": True, "stdout": "ok", "stderr": "deprecation warning"},
        ):
            result = tool._run("status")
        assert "Warnings:" in result
        assert "deprecation warning" in result

    def test_cli_skill_failure(self):
        tool = self._tool()
        with patch(
            "core.skill_adapter.execute_atom_cli_command",
            return_value={"success": False, "stdout": "", "stderr": "boom"},
        ):
            result = tool._run("status")
        assert result == "Command failed:\nboom"

    def test_cli_skill_exception(self):
        tool = self._tool()
        with patch(
            "core.skill_adapter.execute_atom_cli_command",
            side_effect=RuntimeError("subprocess died"),
        ):
            result = tool._run("status")
        assert result.startswith("ERROR: Failed to execute CLI skill")

    def test_cli_skill_extracts_command_from_id(self):
        tool = self._tool(skill_id="atom-config")
        with patch("core.skill_adapter.execute_atom_cli_command",
                   return_value={"success": True, "stdout": "ok", "stderr": ""}) as exec_mock:
            tool._run("show daemon")
        assert exec_mock.call_args[0][0] == "config"


class TestParseCliArgs:
    def test_port_flag(self):
        tool = CommunitySkillTool()
        assert tool._parse_cli_args("port 3000", "daemon") == ["--port", "3000"]

    def test_host_flag(self):
        tool = CommunitySkillTool()
        assert tool._parse_cli_args("host 0.0.0.0", "daemon") == ["--host", "0.0.0.0"]

    def test_workers_flag(self):
        tool = CommunitySkillTool()
        assert tool._parse_cli_args("worker 4", "daemon") == ["--workers", "4"]

    def test_boolean_flags(self):
        tool = CommunitySkillTool()
        args = tool._parse_cli_args("start with host mount in development foreground", "daemon")
        assert "--host-mount" in args
        assert "--dev" in args
        assert "--foreground" in args

    def test_config_show_daemon(self):
        tool = CommunitySkillTool()
        args = tool._parse_cli_args("show daemon config", "config")
        assert "--show-daemon" in args

    def test_plain_query_returns_none(self):
        tool = CommunitySkillTool()
        assert tool._parse_cli_args("how are you", "daemon") is None


# ============================================================================
# CommunitySkillTool — prompt-only + python skills
# ============================================================================

class TestPromptSkill:
    def test_double_brace_interpolation(self):
        tool = CommunitySkillTool(
            skill_id="p1", skill_type="prompt_only", skill_content="Hello {{query}}!"
        )
        assert tool._run("world") == "Hello world!"

    def test_single_brace_interpolation(self):
        tool = CommunitySkillTool(
            skill_id="p2", skill_type="prompt_only", skill_content="Do: {query}"
        )
        assert tool._run("stuff") == "Do: stuff"

    def test_no_placeholder_appends_query(self):
        tool = CommunitySkillTool(
            skill_id="p3", skill_type="prompt_only", skill_content="Static instructions"
        )
        result = tool._run("q")
        assert "Static instructions" in result
        assert "User Query: q" in result

    def test_format_failure_returns_error(self):
        tool = CommunitySkillTool(
            skill_id="p4", skill_type="prompt_only", skill_content="{query} missing {other}"
        )
        result = tool._run("q")
        assert result.startswith("ERROR: Failed to format prompt")

    def test_arun_delegates_to_run(self):
        tool = CommunitySkillTool(
            skill_id="p5", skill_type="prompt_only", skill_content="Hello {{query}}"
        )
        import asyncio
        assert asyncio.run(tool._arun("x")) == "Hello x"

    def test_unknown_skill_type_raises(self):
        tool = CommunitySkillTool(skill_id="u1", skill_type="weird")
        with pytest.raises(ValueError, match="Unknown skill type"):
            tool._run("q")


class TestPythonSkill:
    def test_sandbox_disabled_raises(self):
        tool = CommunitySkillTool(
            skill_id="py1", skill_type="python_code", skill_content="def execute(query): pass",
            sandbox_enabled=False,
        )
        with pytest.raises(RuntimeError, match="sandbox execution"):
            tool._run("q")

    def test_sandboxed_success(self):
        tool = CommunitySkillTool(
            skill_id="py2", skill_type="python_code",
            skill_content="def execute(query):\n    return 'hi'",
            sandbox_enabled=True,
        )
        with patch("core.skill_sandbox.HazardSandbox") as hs:
            hs.return_value.execute_python.return_value = "sandbox output"
            result = tool._run("q")
        assert result == "sandbox output"
        hs.return_value.execute_python.assert_called_once_with(
            code=ANY, inputs={"query": "q"},
            timeout_seconds=300, memory_limit="256m", cpu_limit=0.5,
        )

    def test_sandbox_docker_not_running(self):
        tool = CommunitySkillTool(
            skill_id="py3", skill_type="python_code", skill_content="def execute(query): pass",
            sandbox_enabled=True,
        )
        with patch("core.skill_sandbox.HazardSandbox") as hs:
            hs.return_value.execute_python.side_effect = RuntimeError("Docker daemon is not running")
            result = tool._run("q")
        assert result == "SANDBOX_ERROR: Docker is not running. Please start Docker to execute Python skills."

    def test_sandbox_other_runtime_error_raises(self):
        tool = CommunitySkillTool(
            skill_id="py4", skill_type="python_code", skill_content="def execute(query): pass",
            sandbox_enabled=True,
        )
        with patch("core.skill_sandbox.HazardSandbox") as hs:
            hs.return_value.execute_python.side_effect = RuntimeError("different error")
            with pytest.raises(RuntimeError, match="different error"):
                tool._run("q")

    def test_sandbox_generic_exception(self):
        tool = CommunitySkillTool(
            skill_id="py5", skill_type="python_code", skill_content="def execute(query): pass",
            sandbox_enabled=True,
        )
        with patch("core.skill_sandbox.HazardSandbox") as hs:
            hs.return_value.execute_python.side_effect = ValueError("oops")
            result = tool._run("q")
        assert result.startswith("EXECUTION_ERROR:")


class TestPythonSkillWithPackages:
    def _tool(self, packages=("numpy",)):
        return CommunitySkillTool(
            name="numpy skill",
            skill_id="pkg1",
            skill_type="python_code",
            skill_content="def execute(query):\n    import numpy\n    return query",
            packages=list(packages),
        )

    def test_install_success_with_vulnerabilities(self):
        tool = self._tool()
        with patch("core.package_installer.PackageInstaller") as pi:
            pi.return_value.install_packages.return_value = {
                "success": True,
                "image_tag": "atom-skill:numpy-v1",
                "vulnerabilities": [{"id": "CVE-1"}],
            }
            pi.return_value.execute_with_packages.return_value = "executed"
            result = tool._run("q")
        assert result == "executed"
        pi.return_value.install_packages.assert_called_once()
        assert pi.return_value.install_packages.call_args[1]["scan_for_vulnerabilities"] is True
        pi.return_value.execute_with_packages.assert_called_once()

    def test_install_success_no_vulnerabilities(self):
        tool = self._tool()
        with patch("core.package_installer.PackageInstaller") as pi:
            pi.return_value.install_packages.return_value = {"success": True, "image_tag": "t"}
            pi.return_value.execute_with_packages.return_value = "out"
            assert tool._run("q") == "out"

    def test_install_failure(self):
        tool = self._tool()
        with patch("core.package_installer.PackageInstaller") as pi:
            pi.return_value.install_packages.return_value = {
                "success": False, "error": "Failed to build Docker image: disk full",
            }
            result = tool._run("q")
        assert result == "PACKAGE_INSTALLATION_ERROR: Failed to build Docker image: disk full"

    def test_execution_failure(self):
        tool = self._tool()
        with patch("core.package_installer.PackageInstaller") as pi:
            pi.return_value.install_packages.return_value = {"success": True, "image_tag": "t"}
            pi.return_value.execute_with_packages.side_effect = RuntimeError("run failed")
            result = tool._run("q")
        assert result == "PACKAGE_EXECUTION_ERROR: run failed"


class TestExtractFunctionCode:
    def test_adds_wrapper_when_missing(self):
        tool = CommunitySkillTool(skill_id="e1", skill_type="python_code",
                                  skill_content="def execute(query):\n    return query")
        code = tool._extract_function_code()
        assert "result = execute(query)" in code
        assert "print(result)" in code

    def test_keeps_existing_wrapper(self):
        content = "def execute(query):\n    return query\n\nresult = execute(query)\nprint(result)"
        tool = CommunitySkillTool(skill_id="e2", skill_type="python_code", skill_content=content)
        assert tool._extract_function_code() == content.strip()


# ============================================================================
# Factory
# ============================================================================

class TestCreateCommunityTool:
    def test_explicit_fields(self):
        tool = create_community_tool({
            "name": "skill-a",
            "description": "desc",
            "skill_type": "python_code",
            "skill_content": "code",
            "skill_id": "sid-1",
            "sandbox_enabled": True,
            "packages": ["numpy"],
        })
        assert tool.name == "skill-a"
        assert tool.skill_id == "sid-1"
        assert tool.skill_type == "python_code"
        assert tool.sandbox_enabled is True
        assert tool.packages == ["numpy"]

    def test_defaults(self):
        tool = create_community_tool({"name": "bare"})
        assert tool.skill_type == "prompt_only"
        assert tool.skill_id == "bare"
        assert tool.skill_content == ""
        assert tool.packages == []
        assert tool.sandbox_enabled is False


# ============================================================================
# NodeJsSkillAdapter
# ============================================================================

class TestNodeJsAdapter:
    def test_init_wiring(self):
        adapter = NodeJsSkillAdapter(
            skill_id="ns-1", code="console.log(1)", node_packages=["lodash@4.17.21"],
            package_manager="yarn", agent_id="ag-1",
        )
        assert adapter.skill_id == "ns-1"
        assert adapter.code == "console.log(1)"
        assert adapter.node_packages == ["lodash@4.17.21"]
        assert adapter.package_manager == "yarn"
        assert adapter.agent_id == "ag-1"

    def test_installer_property_lazy_loads(self):
        adapter = NodeJsSkillAdapter(skill_id="ns-2", code="", node_packages=[])
        with patch("core.npm_package_installer.NpmPackageInstaller") as npi:
            installer = adapter.installer
        assert installer is npi.return_value
        assert adapter._installer is npi.return_value
        with patch("core.npm_package_installer.NpmPackageInstaller") as npi2:
            assert adapter.installer is installer  # cached, no second instantiation
        npi2.assert_not_called()

    def test_governance_property_lazy_loads(self):
        adapter = NodeJsSkillAdapter(skill_id="ns-3", code="", node_packages=[])
        with patch("core.package_governance_service.PackageGovernanceService") as pgs:
            gov = adapter.governance
        assert gov is pgs.return_value
        assert adapter._governance is pgs.return_value

    def test_parse_npm_package_scoped_with_version(self):
        adapter = NodeJsSkillAdapter(skill_id="ns-4", code="", node_packages=[])
        assert adapter._parse_npm_package("@scope/name@^1.0.0") == ("@scope/name", "^1.0.0")

    def test_parse_npm_package_scoped_bare(self):
        adapter = NodeJsSkillAdapter(skill_id="ns-5", code="", node_packages=[])
        assert adapter._parse_npm_package("@scope/name") == ("@scope/name", "latest")

    def test_parse_npm_package_regular(self):
        adapter = NodeJsSkillAdapter(skill_id="ns-6", code="", node_packages=[])
        assert adapter._parse_npm_package("lodash@4.17.21") == ("lodash", "4.17.21")
        assert adapter._parse_npm_package("express") == ("express", "latest")


class TestInstallNpmDependencies:
    def _adapter(self):
        adapter = NodeJsSkillAdapter(
            skill_id="npm-1", code="", node_packages=["lodash@4.17.21"],
        )
        adapter._governance = MagicMock()
        adapter._installer = MagicMock()
        return adapter

    def _db_ctx(self):
        ctx = MagicMock()
        fake_db = MagicMock()
        ctx.__enter__.return_value = fake_db
        return ctx, fake_db

    def test_governance_blocked(self):
        adapter = self._adapter()
        adapter._governance.check_package_permission.return_value = {
            "allowed": False, "reason": "policy denies lodash",
        }
        _, fake_db = self._db_ctx()
        with patch("core.database.SessionLocal", return_value=fake_db):
            result = adapter.install_npm_dependencies()
        assert result["success"] is False
        assert "blocked by governance" in result["error"]
        assert result["package"] == "lodash"
        fake_db.close.assert_called_once()

    def test_malicious_scripts(self):
        adapter = self._adapter()
        adapter._governance.check_package_permission.return_value = {"allowed": True}
        with patch("core.database.get_db_session") as gds, patch(
            "core.npm_script_analyzer.NpmScriptAnalyzer"
        ) as analyzer:
            analyzer.return_value.analyze_package_scripts.return_value = {
                "malicious": True, "warnings": ["postinstall: rm -rf /"],
            }
            result = adapter.install_npm_dependencies()
        assert result["success"] is False
        assert "Malicious" in result["error"]

    def test_suspicious_scripts_warns_but_installs(self):
        adapter = self._adapter()
        adapter._governance.check_package_permission.return_value = {"allowed": True}
        adapter._installer.install_packages.return_value = {"success": True, "image_tag": "img:1"}
        with patch("core.database.get_db_session") as gds, patch(
            "core.npm_script_analyzer.NpmScriptAnalyzer"
        ) as analyzer:
            analyzer.return_value.analyze_package_scripts.return_value = {
                "malicious": False, "warnings": ["preinstall script found"],
            }
            result = adapter.install_npm_dependencies()
        assert result["success"] is True
        assert result["image_tag"] == "img:1"

    def test_installer_failure(self):
        adapter = self._adapter()
        adapter._governance.check_package_permission.return_value = {"allowed": True}
        adapter._installer.install_packages.return_value = {
            "success": False, "error": "npm install failed",
        }
        with patch("core.database.get_db_session") as gds, patch(
            "core.npm_script_analyzer.NpmScriptAnalyzer"
        ) as analyzer:
            analyzer.return_value.analyze_package_scripts.return_value = {
                "malicious": False, "warnings": [],
            }
            result = adapter.install_npm_dependencies()
        assert result["success"] is False
        assert result["error"] == "npm install failed"

    def test_success_closes_db(self):
        adapter = self._adapter()
        adapter._governance.check_package_permission.return_value = {"allowed": True}
        adapter._installer.install_packages.return_value = {
            "success": True, "image_tag": "img:9", "vulnerabilities": [{"id": "CVE-2"}],
        }
        _, fake_db = self._db_ctx()
        with patch("core.database.SessionLocal", return_value=fake_db), patch(
            "core.npm_script_analyzer.NpmScriptAnalyzer"
        ) as analyzer:
            analyzer.return_value.analyze_package_scripts.return_value = {
                "malicious": False, "warnings": [],
            }
            result = adapter.install_npm_dependencies()
        assert result["success"] is True
        assert result["vulnerabilities"] == [{"id": "CVE-2"}]
        fake_db.close.assert_called_once()


class TestExecuteNodejsCode:
    def test_success(self):
        adapter = NodeJsSkillAdapter(skill_id="ex-1", code="c", node_packages=[])
        adapter._installer = MagicMock()
        adapter._installer.execute_with_packages.return_value = "node output"
        result = adapter.execute_nodejs_code("query")
        assert result == "node output"
        adapter._installer.execute_with_packages.assert_called_once_with(
            skill_id="ex-1", code="c", inputs={"query": "query"}, timeout_seconds=300,
        )

    def test_exception_returns_error_string(self):
        adapter = NodeJsSkillAdapter(skill_id="ex-2", code="c", node_packages=[])
        adapter._installer = MagicMock()
        adapter._installer.execute_with_packages.side_effect = RuntimeError("container down")
        result = adapter.execute_nodejs_code("query")
        assert result == "Node.js execution failed: container down"


class TestNodeJsRun:
    def test_run_success(self):
        adapter = NodeJsSkillAdapter(skill_id="run-1", code="c", node_packages=["x"])
        adapter._governance = MagicMock()
        adapter._installer = MagicMock()
        adapter._installer.install_packages.return_value = {"success": True, "image_tag": "img"}
        adapter._installer.execute_with_packages.return_value = "done"
        with patch("core.database.get_db_session") as gds, patch(
            "core.npm_script_analyzer.NpmScriptAnalyzer"
        ) as analyzer:
            analyzer.return_value.analyze_package_scripts.return_value = {
                "malicious": False, "warnings": [],
            }
            result = adapter._run({"query": "hello"})
        assert result == "done"
        adapter._installer.execute_with_packages.assert_called_once()

    def test_run_install_failure(self):
        adapter = NodeJsSkillAdapter(skill_id="run-2", code="c", node_packages=["x"])
        adapter._governance = MagicMock()
        adapter._governance.check_package_permission.return_value = {"allowed": False}
        with patch("core.database.get_db_session") as gds:
            result = adapter._run({"query": "hello"})
        assert result.startswith("NPM_INSTALLATION_ERROR:")

    def test_run_execution_exception(self):
        adapter = NodeJsSkillAdapter(skill_id="run-3", code="c", node_packages=["x"])
        adapter._governance = MagicMock()
        adapter._installer = MagicMock()
        adapter._installer.install_packages.return_value = {"success": True, "image_tag": "img"}
        adapter._installer.execute_with_packages.side_effect = RuntimeError("kaboom")
        with patch("core.database.get_db_session") as gds, patch(
            "core.npm_script_analyzer.NpmScriptAnalyzer"
        ) as analyzer:
            analyzer.return_value.analyze_package_scripts.return_value = {
                "malicious": False, "warnings": [],
            }
            result = adapter._run({"query": "hello"})
        assert result == "Node.js execution failed: kaboom"

    def test_run_outer_exception_prefixed(self):
        adapter = NodeJsSkillAdapter(skill_id="run-5", code="c", node_packages=["x"])
        with patch.object(
            NodeJsSkillAdapter, "install_npm_dependencies", side_effect=RuntimeError("boom")
        ):
            result = adapter._run({"query": "hello"})
        assert result == "NODEJS_EXECUTION_ERROR: boom"

    def test_arun_delegates(self):
        adapter = NodeJsSkillAdapter(skill_id="run-4", code="c", node_packages=[])
        adapter._installer = MagicMock()
        adapter._installer.execute_with_packages.return_value = "sync done"
        import asyncio
        result = asyncio.run(adapter._arun({"query": "q"}))
        assert result == "sync done"
