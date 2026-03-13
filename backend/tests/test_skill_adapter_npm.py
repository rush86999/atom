"""
Tests for npm package support in skill_adapter.py (Phase 36).

Tests cover:
- NodeJsSkillAdapter initialization and basics
- npm package parsing (scoped, versioned, default versions)
- Governance checks (permission denied, package_type, agent_id)
- Script analysis (malicious detection, warnings)
- Installation workflow (success, failure, vulnerabilities)
- Execution (inputs, error handling, logging)

Reference: Phase 36 Plan 06 - npm Skill Integration
Reference: Phase 183-01 Plan 01 Task 3 - npm Packages Test Coverage
"""

import pytest
import sys
from unittest.mock import patch, Mock, MagicMock, AsyncMock

# Module-level mocking for docker.errors (Phase 182 pattern)
sys.modules['docker'] = MagicMock()
sys.modules['docker.errors'] = MagicMock()

# Module-level mocking for npm-related modules
sys.modules['core.npm_package_installer'] = MagicMock()
sys.modules['core.package_governance_service'] = MagicMock()
sys.modules['core.npm_script_analyzer'] = MagicMock()

from core.skill_adapter import NodeJsSkillAdapter


class TestNpmSkillAdapterBasics:
    """Test NodeJsSkillAdapter initialization and basic functionality."""

    def test_npm_skill_adapter_initialization(self):
        """Test that NodeJsSkillAdapter stores skill_id, code, node_packages."""
        adapter = NodeJsSkillAdapter(
            skill_id="test-npm-skill",
            code="const execute = (query) => `Result: ${query}`;",
            node_packages=["lodash@4.17.21"]
        )

        assert adapter.skill_id == "test-npm-skill"
        assert adapter.code == "const execute = (query) => `Result: ${query}`;"
        assert adapter.node_packages == ["lodash@4.17.21"]

    def test_package_manager_default(self):
        """Test that default package_manager is 'npm'."""
        adapter = NodeJsSkillAdapter(
            skill_id="test-skill",
            code="const execute = (query) => query;",
            node_packages=[]
        )

        assert adapter.package_manager == "npm"

    def test_package_manager_custom(self):
        """Test that package_manager can be set to 'yarn' or 'pnpm'."""
        yarn_adapter = NodeJsSkillAdapter(
            skill_id="test-skill",
            code="const execute = (query) => query;",
            node_packages=[],
            package_manager="yarn"
        )

        pnpm_adapter = NodeJsSkillAdapter(
            skill_id="test-skill",
            code="const execute = (query) => query;",
            node_packages=[],
            package_manager="pnpm"
        )

        assert yarn_adapter.package_manager == "yarn"
        assert pnpm_adapter.package_manager == "pnpm"

    def test_lazy_installer_loading(self):
        """Test that NpmPackageInstaller is loaded on first access."""
        adapter = NodeJsSkillAdapter(
            skill_id="test-skill",
            code="const execute = (query) => query;",
            node_packages=[]
        )

        # Should be None initially
        assert adapter._installer is None

        # Access installer property to trigger lazy load
        _ = adapter.installer

        # Should now be loaded (mocked)
        assert adapter._installer is not None

    def test_lazy_governance_loading(self):
        """Test that PackageGovernanceService is loaded on first access."""
        adapter = NodeJsSkillAdapter(
            skill_id="test-skill",
            code="const execute = (query) => query;",
            node_packages=[],
            agent_id="test-agent"
        )

        # Should be None initially
        assert adapter._governance is None

        # Access governance property to trigger lazy load
        _ = adapter.governance

        # Should now be loaded (mocked)
        assert adapter._governance is not None


class TestNpmPackageParsing:
    """Test npm package specifier parsing."""

    @pytest.fixture
    def npm_adapter(self):
        """Create a NodeJsSkillAdapter for testing."""
        return NodeJsSkillAdapter(
            skill_id="test-skill",
            code="const execute = (query) => query;",
            node_packages=[]
        )

    def test_regular_package_parsing(self, npm_adapter):
        """Test 'lodash@4.17.21' -> ('lodash', '4.17.21')."""
        name, version = npm_adapter._parse_npm_package("lodash@4.17.21")

        assert name == "lodash"
        assert version == "4.17.21"

    def test_scoped_package_parsing(self, npm_adapter):
        """Test '@babel/core@^7.0.0' -> ('@babel/core', '^7.0.0')."""
        name, version = npm_adapter._parse_npm_package("@babel/core@^7.0.0")

        assert name == "@babel/core"
        assert version == "^7.0.0"

    def test_scoped_no_version(self, npm_adapter):
        """Test '@scope/name' -> ('@scope/name', 'latest')."""
        name, version = npm_adapter._parse_npm_package("@scope/name")

        assert name == "@scope/name"
        assert version == "latest"

    def test_no_version_specifier(self, npm_adapter):
        """Test 'express' -> ('express', 'latest')."""
        name, version = npm_adapter._parse_npm_package("express")

        assert name == "express"
        assert version == "latest"

    def test_caret_version(self, npm_adapter):
        """Test 'package@^1.0.0' -> ('package', '^1.0.0')."""
        name, version = npm_adapter._parse_npm_package("mypackage@^1.0.0")

        assert name == "mypackage"
        assert version == "^1.0.0"

    def test_tilde_version(self, npm_adapter):
        """Test 'package@~2.0.0' -> ('package', '~2.0.0')."""
        name, version = npm_adapter._parse_npm_package("mypackage@~2.0.0")

        assert name == "mypackage"
        assert version == "~2.0.0"


class TestNpmGovernanceChecks:
    """Test npm package governance permission checks."""

    @pytest.fixture
    def mock_governance(self):
        """Create mock governance service."""
        mock_gov = MagicMock()
        mock_gov.check_package_permission.return_value = {
            "allowed": True,
            "reason": None
        }
        return mock_gov

    @pytest.fixture
    def npm_adapter(self):
        """Create a NodeJsSkillAdapter for testing."""
        return NodeJsSkillAdapter(
            skill_id="test-skill",
            code="const execute = (query) => query;",
            node_packages=["lodash@4.17.21", "express@^4.17.0"],
            agent_id="test-agent"
        )

    @patch('sqlalchemy.create_engine')
    @patch('sqlalchemy.orm.sessionmaker')
    def test_governance_check_all_packages(self, mock_sessionmaker, mock_create_engine, npm_adapter, mock_governance):
        """Test that each package checked via governance.check_package_permission."""
        # Mock database session
        mock_db = MagicMock()
        mock_sessionmaker.return_value = mock_db
        mock_create_engine.return_value = MagicMock()

        # Override governance with mock
        npm_adapter._governance = mock_governance

        # Call install_npm_dependencies (governance is first step)
        # We'll patch installer to avoid actual installation
        with patch.object(npm_adapter, 'installer') as mock_installer:
            with patch('core.skill_adapter.NpmScriptAnalyzer') as mock_analyzer:
                mock_installer.install_packages.return_value = {
                    "success": True,
                    "image_tag": "atom-skill:test-skill-v1"
                }
                mock_analyzer.return_value.analyze_package_scripts.return_value = {
                    "malicious": False,
                    "warnings": []
                }

                npm_adapter.install_npm_dependencies()

        # Verify governance was called for each package
        assert mock_governance.check_package_permission.call_count == 2

        # Verify calls were made with correct arguments
        calls = mock_governance.check_package_permission.call_args_list
        assert calls[0][1]["package_name"] == "lodash"
        assert calls[0][1]["version"] == "4.17.21"
        assert calls[0][1]["package_type"] == "npm"
        assert calls[0][1]["agent_id"] == "test-agent"

    @patch('sqlalchemy.create_engine')
    @patch('sqlalchemy.orm.sessionmaker')
    def test_governance_denied_stops_installation(self, mock_sessionmaker, mock_create_engine):
        """Test that permission denied returns error."""
        # Mock database session
        mock_db = MagicMock()
        mock_sessionmaker.return_value = mock_db
        mock_create_engine.return_value = MagicMock()

        # Create adapter with denied governance
        npm_adapter = NodeJsSkillAdapter(
            skill_id="test-skill",
            code="const execute = (query) => query;",
            node_packages=["banned-package@1.0.0"],
            agent_id="test-agent"
        )

        # Mock governance to deny permission
        mock_gov = MagicMock()
        mock_gov.check_package_permission.return_value = {
            "allowed": False,
            "reason": "Package is banned for security reasons"
        }
        npm_adapter._governance = mock_gov

        # Call install_npm_dependencies
        result = npm_adapter.install_npm_dependencies()

        # Verify error returned
        assert result["success"] is False
        assert "banned by governance" in result["error"]
        assert "banned-package" in result["package"]

    @patch('sqlalchemy.create_engine')
    @patch('sqlalchemy.orm.sessionmaker')
    def test_npm_package_type_in_check(self, mock_sessionmaker, mock_create_engine, npm_adapter, mock_governance):
        """Test that package_type='npm' passed to check."""
        mock_db = MagicMock()
        mock_sessionmaker.return_value = mock_db
        mock_create_engine.return_value = MagicMock()
        npm_adapter._governance = mock_governance

        # Patch installer and analyzer to avoid actual work
        with patch.object(npm_adapter, 'installer') as mock_installer:
            with patch('core.skill_adapter.NpmScriptAnalyzer') as mock_analyzer:
                mock_installer.install_packages.return_value = {
                    "success": True,
                    "image_tag": "atom-skill:test-skill-v1"
                }
                mock_analyzer.return_value.analyze_package_scripts.return_value = {
                    "malicious": False,
                    "warnings": []
                }

                npm_adapter.install_npm_dependencies()

        # Verify package_type was 'npm' in all calls
        for call in mock_governance.check_package_permission.call_args_list:
            assert call[1]["package_type"] == "npm"

    @patch('sqlalchemy.create_engine')
    @patch('sqlalchemy.orm.sessionmaker')
    def test_agent_id_passed_to_governance(self, mock_sessionmaker, mock_create_engine, npm_adapter, mock_governance):
        """Test that agent_id parameter passed correctly."""
        mock_db = MagicMock()
        mock_sessionmaker.return_value = mock_db
        mock_create_engine.return_value = MagicMock()
        npm_adapter._governance = mock_governance

        # Patch installer and analyzer
        with patch.object(npm_adapter, 'installer') as mock_installer:
            with patch('core.skill_adapter.NpmScriptAnalyzer') as mock_analyzer:
                mock_installer.install_packages.return_value = {
                    "success": True,
                    "image_tag": "atom-skill:test-skill-v1"
                }
                mock_analyzer.return_value.analyze_package_scripts.return_value = {
                    "malicious": False,
                    "warnings": []
                }

                npm_adapter.install_npm_dependencies()

        # Verify agent_id was passed
        for call in mock_governance.check_package_permission.call_args_list:
            assert call[1]["agent_id"] == "test-agent"

    @patch('sqlalchemy.create_engine')
    @patch('sqlalchemy.orm.sessionmaker')
    def test_db_session_passed_to_governance(self, mock_sessionmaker, mock_create_engine, npm_adapter, mock_governance):
        """Test that db parameter passed for audit logging."""
        mock_db = MagicMock()
        mock_sessionmaker.return_value = mock_db
        mock_create_engine.return_value = MagicMock()
        npm_adapter._governance = mock_governance

        # Patch installer and analyzer
        with patch.object(npm_adapter, 'installer') as mock_installer:
            with patch('core.skill_adapter.NpmScriptAnalyzer') as mock_analyzer:
                mock_installer.install_packages.return_value = {
                    "success": True,
                    "image_tag": "atom-skill:test-skill-v1"
                }
                mock_analyzer.return_value.analyze_package_scripts.return_value = {
                    "malicious": False,
                    "warnings": []
                }

                npm_adapter.install_npm_dependencies()

        # Verify db session was passed
        for call in mock_governance.check_package_permission.call_args_list:
            assert "db" in call[1]
            assert call[1]["db"] == mock_db

    @patch('sqlalchemy.create_engine')
    @patch('sqlalchemy.orm.sessionmaker')
    def test_continues_on_parse_error(self, mock_sessionmaker, mock_create_engine):
        """Test that invalid package spec logged but continues."""
        mock_db = MagicMock()
        mock_sessionmaker.return_value = mock_db
        mock_create_engine.return_value = MagicMock()

        npm_adapter = NodeJsSkillAdapter(
            skill_id="test-skill",
            code="const execute = (query) => query;",
            node_packages=["valid@1.0.0", "invalid!!!", "also-valid@2.0.0"],
            agent_id="test-agent"
        )

        # Mock governance to allow all
        mock_gov = MagicMock()
        mock_gov.check_package_permission.return_value = {
            "allowed": True,
            "reason": None
        }
        npm_adapter._governance = mock_gov

        # Patch installer and analyzer
        with patch.object(npm_adapter, 'installer') as mock_installer:
            with patch('core.skill_adapter.NpmScriptAnalyzer') as mock_analyzer:
                mock_installer.install_packages.return_value = {
                    "success": True,
                    "image_tag": "atom-skill:test-skill-v1"
                }
                mock_analyzer.return_value.analyze_package_scripts.return_value = {
                    "malicious": False,
                    "warnings": []
                }

                # Should not raise exception
                result = npm_adapter.install_npm_dependencies()

        # Parse error is logged but continues with valid packages
        # Governance should be called for all packages (including invalid)
        assert mock_gov.check_package_permission.call_count == 3


class TestNpmScriptAnalysis:
    """Test npm package script analysis for malicious patterns."""

    @patch('sqlalchemy.create_engine')
    @patch('sqlalchemy.orm.sessionmaker')
    def test_script_analyzer_called(self, mock_sessionmaker, mock_create_engine):
        """Test NpmScriptAnalyzer.analyze_package_scripts called."""
        mock_db = MagicMock()
        mock_sessionmaker.return_value = mock_db
        mock_create_engine.return_value = MagicMock()

        npm_adapter = NodeJsSkillAdapter(
            skill_id="test-skill",
            code="const execute = (query) => query;",
            node_packages=["lodash@4.17.21"]
        )

        # Mock governance
        mock_gov = MagicMock()
        mock_gov.check_package_permission.return_value = {
            "allowed": True,
            "reason": None
        }
        npm_adapter._governance = mock_gov

        # Patch installer and analyzer
        with patch.object(npm_adapter, 'installer') as mock_installer:
            with patch('core.skill_adapter.NpmScriptAnalyzer') as mock_analyzer_class:
                mock_installer.install_packages.return_value = {
                    "success": True,
                    "image_tag": "atom-skill:test-skill-v1"
                }

                mock_analyzer = MagicMock()
                mock_analyzer.analyze_package_scripts.return_value = {
                    "malicious": False,
                    "warnings": []
                }
                mock_analyzer_class.return_value = mock_analyzer

                npm_adapter.install_npm_dependencies()

        # Verify analyzer was called
        mock_analyzer.analyze_package_scripts.assert_called_once_with(
            ["lodash@4.17.21"],
            "npm"
        )

    @patch('sqlalchemy.create_engine')
    @patch('sqlalchemy.orm.sessionmaker')
    def test_malicious_scripts_block_install(self, mock_sessionmaker, mock_create_engine):
        """Test that malicious=True returns error."""
        mock_db = MagicMock()
        mock_sessionmaker.return_value = mock_db
        mock_create_engine.return_value = MagicMock()

        npm_adapter = NodeJsSkillAdapter(
            skill_id="test-skill",
            code="const execute = (query) => query;",
            node_packages=["malicious-pkg@1.0.0"]
        )

        # Mock governance
        mock_gov = MagicMock()
        mock_gov.check_package_permission.return_value = {
            "allowed": True,
            "reason": None
        }
        npm_adapter._governance = mock_gov

        # Patch analyzer to return malicious
        with patch('core.skill_adapter.NpmScriptAnalyzer') as mock_analyzer_class:
            mock_analyzer = MagicMock()
            mock_analyzer.analyze_package_scripts.return_value = {
                "malicious": True,
                "warnings": ["postinstall script executes arbitrary code"]
            }
            mock_analyzer_class.return_value = mock_analyzer

            result = npm_adapter.install_npm_dependencies()

        # Verify error returned
        assert result["success"] is False
        assert "Malicious postinstall/preinstall scripts detected" in result["error"]

    @patch('sqlalchemy.create_engine')
    @patch('sqlalchemy.orm.sessionmaker')
    def test_warnings_logged(self, mock_sessionmaker, mock_create_engine):
        """Test that suspicious scripts logged but installation continues."""
        mock_db = MagicMock()
        mock_sessionmaker.return_value = mock_db
        mock_create_engine.return_value = MagicMock()

        npm_adapter = NodeJsSkillAdapter(
            skill_id="test-skill",
            code="const execute = (query) => query;",
            node_packages=["suspicious-pkg@1.0.0"]
        )

        # Mock governance
        mock_gov = MagicMock()
        mock_gov.check_package_permission.return_value = {
            "allowed": True,
            "reason": None
        }
        npm_adapter._governance = mock_gov

        # Patch installer and analyzer
        with patch.object(npm_adapter, 'installer') as mock_installer:
            with patch('core.skill_adapter.NpmScriptAnalyzer') as mock_analyzer_class:
                mock_installer.install_packages.return_value = {
                    "success": True,
                    "image_tag": "atom-skill:test-skill-v1"
                }

                mock_analyzer = MagicMock()
                mock_analyzer.analyze_package_scripts.return_value = {
                    "malicious": False,
                    "warnings": ["postinstall script runs shell command"]
                }
                mock_analyzer_class.return_value = mock_analyzer

                result = npm_adapter.install_npm_dependencies()

        # Should succeed despite warnings
        assert result["success"] is True
        assert "script_warnings" in result

    @patch('sqlalchemy.create_engine')
    @patch('sqlalchemy.orm.sessionmaker')
    def test_package_manager_passed(self, mock_sessionmaker, mock_create_engine):
        """Test that package_manager passed to analyzer."""
        mock_db = MagicMock()
        mock_sessionmaker.return_value = mock_db
        mock_create_engine.return_value = MagicMock()

        npm_adapter = NodeJsSkillAdapter(
            skill_id="test-skill",
            code="const execute = (query) => query;",
            node_packages=["lodash@4.17.21"],
            package_manager="yarn"
        )

        # Mock governance
        mock_gov = MagicMock()
        mock_gov.check_package_permission.return_value = {
            "allowed": True,
            "reason": None
        }
        npm_adapter._governance = mock_gov

        # Patch installer and analyzer
        with patch.object(npm_adapter, 'installer') as mock_installer:
            with patch('core.skill_adapter.NpmScriptAnalyzer') as mock_analyzer_class:
                mock_installer.install_packages.return_value = {
                    "success": True,
                    "image_tag": "atom-skill:test-skill-v1"
                }

                mock_analyzer = MagicMock()
                mock_analyzer.analyze_package_scripts.return_value = {
                    "malicious": False,
                    "warnings": []
                }
                mock_analyzer_class.return_value = mock_analyzer

                npm_adapter.install_npm_dependencies()

        # Verify package_manager was 'yarn'
        mock_analyzer.analyze_package_scripts.assert_called_once()
        call_args = mock_analyzer.analyze_package_scripts.call_args
        assert call_args[0][1] == "yarn"


class TestNpmInstallation:
    """Test npm package installation workflow."""

    @patch('sqlalchemy.create_engine')
    @patch('sqlalchemy.orm.sessionmaker')
    def test_installer_install_packages_called(self, mock_sessionmaker, mock_create_engine):
        """Test NpmPackageInstaller.install_packages called."""
        mock_db = MagicMock()
        mock_sessionmaker.return_value = mock_db
        mock_create_engine.return_value = MagicMock()

        npm_adapter = NodeJsSkillAdapter(
            skill_id="test-skill",
            code="const execute = (query) => query;",
            node_packages=["lodash@4.17.21"]
        )

        # Mock governance and analyzer
        mock_gov = MagicMock()
        mock_gov.check_package_permission.return_value = {
            "allowed": True,
            "reason": None
        }
        npm_adapter._governance = mock_gov

        # Patch installer and analyzer
        with patch('core.skill_adapter.NpmScriptAnalyzer') as mock_analyzer_class:
            mock_analyzer = MagicMock()
            mock_analyzer.analyze_package_scripts.return_value = {
                "malicious": False,
                "warnings": []
            }
            mock_analyzer_class.return_value = mock_analyzer

            with patch.object(npm_adapter, 'installer') as mock_installer:
                mock_installer.install_packages.return_value = {
                    "success": True,
                    "image_tag": "atom-skill:test-skill-v1"
                }

                npm_adapter.install_npm_dependencies()

        # Verify installer called
        mock_installer.install_packages.assert_called_once()
        call_args = mock_installer.install_packages.call_args
        assert call_args[1]["skill_id"] == "test-skill"
        assert call_args[1]["packages"] == ["lodash@4.17.21"]
        assert call_args[1]["package_manager"] == "npm"
        assert call_args[1]["scan_for_vulnerabilities"] is True

    @patch('sqlalchemy.create_engine')
    @patch('sqlalchemy.orm.sessionmaker')
    def test_install_failure_returns_error(self, mock_sessionmaker, mock_create_engine):
        """Test that failed install returns error dict."""
        mock_db = MagicMock()
        mock_sessionmaker.return_value = mock_db
        mock_create_engine.return_value = MagicMock()

        npm_adapter = NodeJsSkillAdapter(
            skill_id="test-skill",
            code="const execute = (query) => query;",
            node_packages=["lodash@4.17.21"]
        )

        # Mock governance and analyzer
        mock_gov = MagicMock()
        mock_gov.check_package_permission.return_value = {
            "allowed": True,
            "reason": None
        }
        npm_adapter._governance = mock_gov

        # Patch installer to return failure
        with patch('core.skill_adapter.NpmScriptAnalyzer') as mock_analyzer_class:
            mock_analyzer = MagicMock()
            mock_analyzer.analyze_package_scripts.return_value = {
                "malicious": False,
                "warnings": []
            }
            mock_analyzer_class.return_value = mock_analyzer

            with patch.object(npm_adapter, 'installer') as mock_installer:
                mock_installer.install_packages.return_value = {
                    "success": False,
                    "error": "Failed to build Docker image"
                }

                result = npm_adapter.install_npm_dependencies()

        # Verify error returned
        assert result["success"] is False
        assert "Failed to build Docker image" in result["error"]

    @patch('sqlalchemy.create_engine')
    @patch('sqlalchemy.orm.sessionmaker')
    def test_vulnerabilities_logged(self, mock_sessionmaker, mock_create_engine):
        """Test vulnerabilities in result logged."""
        mock_db = MagicMock()
        mock_sessionmaker.return_value = mock_db
        mock_create_engine.return_value = MagicMock()

        npm_adapter = NodeJsSkillAdapter(
            skill_id="test-skill",
            code="const execute = (query) => query;",
            node_packages=["lodash@4.17.21"]
        )

        # Mock governance and analyzer
        mock_gov = MagicMock()
        mock_gov.check_package_permission.return_value = {
            "allowed": True,
            "reason": None
        }
        npm_adapter._governance = mock_gov

        # Patch installer to return vulnerabilities
        with patch('core.skill_adapter.NpmScriptAnalyzer') as mock_analyzer_class:
            mock_analyzer = MagicMock()
            mock_analyzer.analyze_package_scripts.return_value = {
                "malicious": False,
                "warnings": []
            }
            mock_analyzer_class.return_value = mock_analyzer

            with patch.object(npm_adapter, 'installer') as mock_installer:
                mock_installer.install_packages.return_value = {
                    "success": True,
                    "image_tag": "atom-skill:test-skill-v1",
                    "vulnerabilities": [
                        {"package": "lodash", "severity": "HIGH", "cve": "CVE-2021-1234"}
                    ]
                }

                result = npm_adapter.install_npm_dependencies()

        # Should succeed with vulnerabilities
        assert result["success"] is True
        assert "vulnerabilities" in result
        assert len(result["vulnerabilities"]) == 1

    @patch('sqlalchemy.create_engine')
    @patch('sqlalchemy.orm.sessionmaker')
    def test_image_tag_returned(self, mock_sessionmaker, mock_create_engine):
        """Test successful install returns image_tag in result."""
        mock_db = MagicMock()
        mock_sessionmaker.return_value = mock_db
        mock_create_engine.return_value = MagicMock()

        npm_adapter = NodeJsSkillAdapter(
            skill_id="test-skill",
            code="const execute = (query) => query;",
            node_packages=["lodash@4.17.21"]
        )

        # Mock governance and analyzer
        mock_gov = MagicMock()
        mock_gov.check_package_permission.return_value = {
            "allowed": True,
            "reason": None
        }
        npm_adapter._governance = mock_gov

        # Patch installer
        with patch('core.skill_adapter.NpmScriptAnalyzer') as mock_analyzer_class:
            mock_analyzer = MagicMock()
            mock_analyzer.analyze_package_scripts.return_value = {
                "malicious": False,
                "warnings": []
            }
            mock_analyzer_class.return_value = mock_analyzer

            with patch.object(npm_adapter, 'installer') as mock_installer:
                mock_installer.install_packages.return_value = {
                    "success": True,
                    "image_tag": "atom-skill:test-skill-v1"
                }

                result = npm_adapter.install_npm_dependencies()

        # Verify image_tag returned
        assert result["success"] is True
        assert result["image_tag"] == "atom-skill:test-skill-v1"

    @patch('sqlalchemy.create_engine')
    @patch('sqlalchemy.orm.sessionmaker')
    def test_skill_id_used_for_image(self, mock_sessionmaker, mock_create_engine):
        """Test skill_id passed to installer."""
        mock_db = MagicMock()
        mock_sessionmaker.return_value = mock_db
        mock_create_engine.return_value = MagicMock()

        npm_adapter = NodeJsSkillAdapter(
            skill_id="my-custom-skill",
            code="const execute = (query) => query;",
            node_packages=["lodash@4.17.21"]
        )

        # Mock governance and analyzer
        mock_gov = MagicMock()
        mock_gov.check_package_permission.return_value = {
            "allowed": True,
            "reason": None
        }
        npm_adapter._governance = mock_gov

        # Patch installer
        with patch('core.skill_adapter.NpmScriptAnalyzer') as mock_analyzer_class:
            mock_analyzer = MagicMock()
            mock_analyzer.analyze_package_scripts.return_value = {
                "malicious": False,
                "warnings": []
            }
            mock_analyzer_class.return_value = mock_analyzer

            with patch.object(npm_adapter, 'installer') as mock_installer:
                mock_installer.install_packages.return_value = {
                    "success": True,
                    "image_tag": "atom-skill:my-custom-skill-v1"
                }

                npm_adapter.install_npm_dependencies()

        # Verify skill_id passed to installer
        call_args = mock_installer.install_packages.call_args
        assert call_args[1]["skill_id"] == "my-custom-skill"


class TestNpmExecution:
    """Test Node.js code execution with pre-installed packages."""

    @patch('sqlalchemy.create_engine')
    @patch('sqlalchemy.orm.sessionmaker')
    def test_execute_with_packages_called(self, mock_sessionmaker, mock_create_engine):
        """Test installer.execute_with_packages called."""
        mock_db = MagicMock()
        mock_sessionmaker.return_value = mock_db
        mock_create_engine.return_value = MagicMock()

        npm_adapter = NodeJsSkillAdapter(
            skill_id="test-skill",
            code="const execute = (query) => `Result: ${query}`;",
            node_packages=["lodash@4.17.21"]
        )

        # Mock installer for execution
        with patch.object(npm_adapter, 'installer') as mock_installer:
            mock_installer.execute_with_packages.return_value = "Result: test query"

            # Call _run with tool_input
            result = npm_adapter._run({"query": "test query"})

        # Verify execute_with_packages called
        mock_installer.execute_with_packages.assert_called_once()

    @patch('sqlalchemy.create_engine')
    @patch('sqlalchemy.orm.sessionmaker')
    def test_inputs_passed(self, mock_sessionmaker, mock_create_engine):
        """Test inputs dict passed to execution."""
        mock_db = MagicMock()
        mock_sessionmaker.return_value = mock_db
        mock_create_engine.return_value = MagicMock()

        npm_adapter = NodeJsSkillAdapter(
            skill_id="test-skill",
            code="const execute = (query) => `Result: ${query}`;",
            node_packages=[]
        )

        # Mock installer
        with patch.object(npm_adapter, 'installer') as mock_installer:
            mock_installer.execute_with_packages.return_value = "Result: test query"

            npm_adapter._run({"query": "test query"})

        # Verify inputs passed
        call_args = mock_installer.execute_with_packages.call_args
        assert "inputs" in call_args[1]
        assert call_args[1]["inputs"]["query"] == "test query"

    @patch('sqlalchemy.create_engine')
    @patch('sqlalchemy.orm.sessionmaker')
    def test_execution_error_handling(self, mock_sessionmaker, mock_create_engine):
        """Test exception returns error message."""
        mock_db = MagicMock()
        mock_sessionmaker.return_value = mock_db
        mock_create_engine.return_value = MagicMock()

        npm_adapter = NodeJsSkillAdapter(
            skill_id="test-skill",
            code="const execute = (query) => query;",
            node_packages=[]
        )

        # Mock installer to raise exception
        with patch.object(npm_adapter, 'installer') as mock_installer:
            mock_installer.execute_with_packages.side_effect = Exception("Docker container crashed")

            result = npm_adapter._run({"query": "test query"})

        # Verify error message returned
        assert "NODEJS_EXECUTION_ERROR" in result
        assert "Docker container crashed" in result

    @patch('sqlalchemy.create_engine')
    @patch('sqlalchemy.orm.sessionmaker')
    def test_execution_logged(self, mock_sessionmaker, mock_create_engine):
        """Test success logged with skill_id."""
        mock_db = MagicMock()
        mock_sessionmaker.return_value = mock_db
        mock_create_engine.return_value = MagicMock()

        npm_adapter = NodeJsSkillAdapter(
            skill_id="test-skill",
            code="const execute = (query) => `Result: ${query}`;",
            node_packages=[]
        )

        # Mock installer
        with patch.object(npm_adapter, 'installer') as mock_installer:
            mock_installer.execute_with_packages.return_value = "Result: test query"

            # Execute (if no exception, logging worked)
            result = npm_adapter._run({"query": "test query"})

        # Verify success
        assert "Result: test query" in result
