"""
Integration tests for npm package support in Community Skills system.

Phase 36 Plan 06 - Task 5: Comprehensive integration test suite

Tests cover:
- SkillParser node_packages parsing
- NodeJsSkillAdapter npm installation and execution
- SkillRegistryService npm workflow with audit logging
- End-to-end skill import with npm packages
- Governance checks and audit logging verification
"""
import pytest
from typing import List
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.skill_parser import SkillParser
from core.skill_adapter import NodeJsSkillAdapter
from core.skill_registry_service import SkillRegistryService
from core.models import AuditLog, Base


# Fixtures

@pytest.fixture
def db_session():
    """Create test database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def skill_parser():
    """Create SkillParser instance."""
    return SkillParser()


@pytest.fixture
def npm_skill_content():
    """Sample SKILL.md with npm packages."""
    return """---
name: "Web Scraper Skill"
description: "Scrape websites using axios and cheerio"
node_packages:
  - axios@^1.6.0
  - cheerio@1.0.0
package_manager: npm
---

This skill scrapes websites using axios and cheerio.

```javascript
const axios = require('axios');
const cheerio = require('cheerio');

async function execute(query) {
  const response = await axios.get(query);
  const $ = cheerio.load(response.data);
  return $('title').text();
}

module.exports = { execute };
```
"""


@pytest.fixture
def mixed_skill_content():
    """Sample SKILL.md with both Python and npm packages."""
    return """---
name: "Hybrid Skill"
description: "Uses both Python and npm packages"
packages:
  - requests==2.31.0
node_packages:
  - lodash@4.17.21
package_manager: npm
---

This skill demonstrates mixed package support.
"""


# SkillParser Tests

class TestSkillParserNodePackages:
    """Test SkillParser node_packages parsing."""

    def test_parse_node_packages_simple(self, skill_parser, npm_skill_content):
        """Test parsing simple npm packages."""
        import frontmatter
        post = frontmatter.loads(npm_skill_content)
        metadata = post.metadata

        node_packages = skill_parser._extract_node_packages(metadata, "test_skill")
        assert len(node_packages) == 2
        assert "axios@^1.6.0" in node_packages
        assert "cheerio@1.0.0" in node_packages

    def test_parse_node_packages_with_version_ranges(self, skill_parser):
        """Test parsing packages with semver ranges."""
        metadata = {
            'node_packages': [
                'lodash@4.17.21',
                'express@^4.18.0',
                'axios@~1.6.0'
            ]
        }

        node_packages = skill_parser._extract_node_packages(metadata, "test")
        assert len(node_packages) == 3
        assert 'lodash@4.17.21' in node_packages
        assert 'express@^4.18.0' in node_packages

    def test_parse_package_manager_npm(self, skill_parser):
        """Test parsing npm package manager."""
        metadata = {'package_manager': 'npm'}
        package_manager = skill_parser._extract_package_manager(metadata, "test")
        assert package_manager == 'npm'

    def test_parse_package_manager_yarn(self, skill_parser):
        """Test parsing yarn package manager."""
        metadata = {'package_manager': 'yarn'}
        package_manager = skill_parser._extract_package_manager(metadata, "test")
        assert package_manager == 'yarn'

    def test_parse_package_manager_pnpm(self, skill_parser):
        """Test parsing pnpm package manager."""
        metadata = {'package_manager': 'pnpm'}
        package_manager = skill_parser._extract_package_manager(metadata, "test")
        assert package_manager == 'pnpm'

    def test_parse_package_manager_default(self, skill_parser):
        """Test default package manager when not specified."""
        metadata = {}
        package_manager = skill_parser._extract_package_manager(metadata, "test")
        assert package_manager == 'npm'

    def test_parse_package_manager_invalid(self, skill_parser):
        """Test invalid package manager defaults to npm."""
        metadata = {'package_manager': 'invalid_manager'}
        package_manager = skill_parser._extract_package_manager(metadata, "test")
        assert package_manager == 'npm'

    def test_validate_npm_package_format_valid(self, skill_parser):
        """Test valid npm package format validation."""
        assert skill_parser._validate_npm_package_format("lodash@4.17.21")
        assert skill_parser._validate_npm_package_format("express@^4.18.0")
        assert skill_parser._validate_npm_package_format("axios")
        assert skill_parser._validate_npm_package_format("@babel/core")

    def test_validate_npm_package_format_invalid(self, skill_parser):
        """Test invalid npm package format validation."""
        assert not skill_parser._validate_npm_package_format("")
        assert not skill_parser._validate_npm_package_format("   ")
        assert not skill_parser._validate_npm_package_format(None)

    def test_parse_mixed_packages(self, skill_parser, mixed_skill_content):
        """Test parsing both Python and npm packages."""
        import frontmatter
        post = frontmatter.loads(mixed_skill_content)
        metadata = post.metadata

        python_packages = skill_parser._extract_packages(metadata, "test")
        node_packages = skill_parser._extract_node_packages(metadata, "test")

        assert len(python_packages) == 1
        assert 'requests==2.31.0' in python_packages
        assert len(node_packages) == 1
        assert 'lodash@4.17.21' in node_packages


# NodeJsSkillAdapter Tests

class TestNodeJsSkillAdapter:
    """Test NodeJsSkillAdapter npm installation and execution."""

    @patch('core.npm_package_installer.NpmPackageInstaller')
    @patch('core.package_governance_service.PackageGovernanceService')
    def test_nodejs_skill_adapter_initialization(self, mock_governance, mock_installer):
        """Test NodeJsSkillAdapter initialization."""
        adapter = NodeJsSkillAdapter(
            skill_id="test_skill",
            code="console.log('Hello');",
            node_packages=["lodash@4.17.21"],
            package_manager="npm",
            agent_id="agent123"
        )

        assert adapter.skill_id == "test_skill"
        assert adapter.code == "console.log('Hello');"
        assert adapter.node_packages == ["lodash@4.17.21"]
        assert adapter.package_manager == "npm"
        assert adapter.agent_id == "agent123"

    @patch('core.npm_package_installer.NpmPackageInstaller')
    @patch('core.package_governance_service.PackageGovernanceService')
    def test_parse_npm_package_simple(self, mock_governance, mock_installer):
        """Test parsing simple npm package specifier."""
        adapter = NodeJsSkillAdapter(
            skill_id="test",
            code="",
            node_packages=[]
        )

        name, version = adapter._parse_npm_package("lodash@4.17.21")
        assert name == "lodash"
        assert version == "4.17.21"

    @patch('core.npm_package_installer.NpmPackageInstaller')
    @patch('core.package_governance_service.PackageGovernanceService')
    def test_parse_npm_package_no_version(self, mock_governance, mock_installer):
        """Test parsing npm package without version."""
        adapter = NodeJsSkillAdapter(
            skill_id="test",
            code="",
            node_packages=[]
        )

        name, version = adapter._parse_npm_package("axios")
        assert name == "axios"
        assert version == "latest"

    @patch('core.npm_package_installer.NpmPackageInstaller')
    @patch('core.package_governance_service.PackageGovernanceService')
    def test_parse_npm_package_scoped(self, mock_governance, mock_installer):
        """Test parsing scoped npm package."""
        adapter = NodeJsSkillAdapter(
            skill_id="test",
            code="",
            node_packages=[]
        )

        name, version = adapter._parse_npm_package("@babel/core")
        assert name == "@babel/core"
        assert version == "latest"

    @patch('core.npm_package_installer.NpmPackageInstaller')
    @patch('core.package_governance_service.PackageGovernanceService')
    @patch('core.npm_script_analyzer.NpmScriptAnalyzer')
    def test_nodejs_skill_adapter_install_success(
        self, mock_script_analyzer, mock_governance_class, mock_installer_class
    ):
        """Test successful npm package installation."""
        # Mock governance
        mock_governance = Mock()
        mock_governance.check_package_permission.return_value = {
            "allowed": True,
            "reason": ""
        }
        mock_governance_class.return_value = mock_governance

        # Mock script analyzer
        mock_script_analyzer_instance = Mock()
        mock_script_analyzer_instance.analyze_package_scripts.return_value = {
            "malicious": False,
            "warnings": []
        }
        mock_script_analyzer.return_value = mock_script_analyzer_instance

        # Mock installer
        mock_installer = Mock()
        mock_installer.install_packages.return_value = {
            "success": True,
            "image_tag": "atom-npm-skill:test_skill-v1",
            "vulnerabilities": []
        }
        mock_installer_class.return_value = mock_installer

        adapter = NodeJsSkillAdapter(
            skill_id="test_skill",
            code="console.log('Hello');",
            node_packages=["lodash@4.17.21"],
            package_manager="npm",
            agent_id="agent123"
        )

        result = adapter.install_npm_dependencies()

        assert result["success"] is True
        assert result["image_tag"] == "atom-npm-skill:test_skill-v1"
        assert mock_governance.check_package_permission.called
        assert mock_installer.install_packages.called

    @patch('core.npm_package_installer.NpmPackageInstaller')
    @patch('core.package_governance_service.PackageGovernanceService')
    @patch('core.npm_script_analyzer.NpmScriptAnalyzer')
    def test_nodejs_skill_adapter_governance_blocked(
        self, mock_script_analyzer, mock_governance_class, mock_installer_class
    ):
        """Test governance blocking npm installation."""
        # Mock governance to block package
        mock_governance = Mock()
        mock_governance.check_package_permission.return_value = {
            "allowed": False,
            "reason": "STUDENT agent cannot install npm packages"
        }
        mock_governance_class.return_value = mock_governance

        adapter = NodeJsSkillAdapter(
            skill_id="test_skill",
            code="",
            node_packages=["lodash@4.17.21"],
            package_manager="npm",
            agent_id="student_agent"
        )

        result = adapter.install_npm_dependencies()

        assert result["success"] is False
        assert "blocked by governance" in result["error"]
        assert result["package"] == "lodash"

    @patch('core.npm_package_installer.NpmPackageInstaller')
    @patch('core.package_governance_service.PackageGovernanceService')
    @patch('core.npm_script_analyzer.NpmScriptAnalyzer')
    def test_nodejs_skill_adapter_scripts_blocked(
        self, mock_script_analyzer, mock_governance_class, mock_installer_class
    ):
        """Test malicious script blocking."""
        # Mock governance to allow
        mock_governance = Mock()
        mock_governance.check_package_permission.return_value = {
            "allowed": True,
            "reason": ""
        }
        mock_governance_class.return_value = mock_governance

        # Mock script analyzer to detect malicious scripts
        mock_script_analyzer_instance = Mock()
        mock_script_analyzer_instance.analyze_package_scripts.return_value = {
            "malicious": True,
            "warnings": ["Suspicious postinstall script detected"]
        }
        mock_script_analyzer.return_value = mock_script_analyzer_instance

        adapter = NodeJsSkillAdapter(
            skill_id="test_skill",
            code="",
            node_packages=["malicious-package@1.0.0"],
            package_manager="npm",
            agent_id="agent123"
        )

        result = adapter.install_npm_dependencies()

        assert result["success"] is False
        assert "malicious postinstall/preinstall scripts" in result["error"]


# SkillRegistryService Tests

class TestSkillRegistryServiceNpmWorkflow:
    """Test SkillRegistryService npm workflow with audit logging."""

    @patch('core.npm_package_installer.NpmPackageInstaller')
    @patch('core.npm_script_analyzer.NpmScriptAnalyzer')
    def test_install_npm_dependencies_for_skill(
        self, mock_script_analyzer_class, mock_installer_class, db_session
    ):
        """Test npm dependency installation workflow."""
        # Setup registry service
        registry = SkillRegistryService(db_session)

        # Mock script analyzer
        mock_script_analyzer = Mock()
        mock_script_analyzer.analyze_package_scripts.return_value = {
            "malicious": False,
            "warnings": []
        }
        mock_script_analyzer_class.return_value = mock_script_analyzer

        # Mock installer
        mock_installer = Mock()
        mock_installer.install_packages.return_value = {
            "success": True,
            "image_tag": "atom-npm-skill:test_skill-v1",
            "vulnerabilities": []
        }
        mock_installer_class.return_value = mock_installer

        # Mock audit service
        with patch('core.audit_service.audit_service') as mock_audit:
            mock_audit.create_package_audit = Mock()

            # Execute installation
            result = registry._install_npm_dependencies_for_skill(
                skill_id="test_skill",
                node_packages=["lodash@4.17.21"],
                package_manager="npm",
                agent_id="agent123",
                db=db_session
            )

            assert result["success"] is True
            assert result["image_tag"] == "atom-npm-skill:test_skill-v1"

            # Verify audit logging was called
            assert mock_audit.create_package_audit.called
            # Should be called twice: once for governance decision, once for installation
            assert mock_audit.create_package_audit.call_count >= 2

    @patch('core.npm_package_installer.NpmPackageInstaller')
    @patch('core.npm_script_analyzer.NpmScriptAnalyzer')
    def test_audit_logging_for_npm_install(
        self, mock_script_analyzer_class, mock_installer_class, db_session
    ):
        """Test audit logging for npm governance decisions and installations."""
        registry = SkillRegistryService(db_session)

        # Mock script analyzer
        mock_script_analyzer = Mock()
        mock_script_analyzer.analyze_package_scripts.return_value = {
            "malicious": False,
            "warnings": []
        }
        mock_script_analyzer_class.return_value = mock_script_analyzer

        # Mock installer
        mock_installer = Mock()
        mock_installer.install_packages.return_value = {
            "success": True,
            "image_tag": "atom-npm-skill:test-v1"
        }
        mock_installer_class.return_value = mock_installer

        # Mock audit service to capture calls
        with patch('core.audit_service.audit_service') as mock_audit:
            audit_calls = []
            def capture_audit(**kwargs):
                audit_calls.append(kwargs)

            mock_audit.create_package_audit.side_effect = capture_audit

            # Execute installation
            result = registry._install_npm_dependencies_for_skill(
                skill_id="test_skill",
                node_packages=["axios@^1.6.0", "lodash@4.17.21"],
                package_manager="npm",
                agent_id="agent123",
                db=db_session
            )

            assert result["success"] is True

            # Verify audit log entries
            assert len(audit_calls) >= 4  # 2 packages * 2 actions (governance + install)

            # Check governance decision audit
            governance_audits = [a for a in audit_calls if a.get('action') == 'governance_decision']
            assert len(governance_audits) == 2

            for audit in governance_audits:
                assert audit['agent_id'] == 'agent123'
                assert audit['package_type'] == 'npm'
                assert audit['skill_id'] == 'test_skill'
                assert audit['governance_decision'] == 'approved'
                assert 'package_name' in audit
                assert 'package_version' in audit

            # Check installation audit
            install_audits = [a for a in audit_calls if a.get('action') == 'install']
            assert len(install_audits) == 2

            for audit in install_audits:
                assert audit['agent_id'] == 'agent123'
                assert audit['package_type'] == 'npm'
                assert audit['skill_id'] == 'test_skill'
                assert audit['governance_decision'] == 'approved'
                assert audit['metadata']['install_success'] is True
                assert 'image_tag' in audit['metadata']

    def test_skill_type_detection_js_file(self, db_session):
        """Test skill type detection for .js file."""
        registry = SkillRegistryService(db_session)

        skill_content = """---
name: "JS Skill"
---

Code file: skill.js
"""
        skill_type = registry.detect_skill_type(skill_content)
        assert skill_type == 'npm'

    def test_skill_type_detection_python_packages(self, db_session):
        """Test skill type detection for Python packages."""
        registry = SkillRegistryService(db_session)

        skill_content = """---
name: "Python Skill"
packages:
  - numpy==1.21.0
---
"""
        skill_type = registry.detect_skill_type(skill_content)
        assert skill_type == 'python'

    def test_skill_type_detection_node_packages(self, db_session):
        """Test skill type detection for npm packages."""
        registry = SkillRegistryService(db_session)

        skill_content = """---
name: "Node Skill"
node_packages:
  - lodash@4.17.21
---
"""
        skill_type = registry.detect_skill_type(skill_content)
        assert skill_type == 'npm'

    def test_skill_type_detection_javascript_code_block(self, db_session):
        """Test skill type detection for JavaScript code block."""
        registry = SkillRegistryService(db_session)

        skill_content = """---
name: "JS Skill"
---

```javascript
console.log('Hello');
```
"""
        skill_type = registry.detect_skill_type(skill_content)
        assert skill_type == 'npm'

    def test_skill_type_detection_python_code_block(self, db_session):
        """Test skill type detection for Python code block."""
        registry = SkillRegistryService(db_session)

        skill_content = """---
name: "Python Skill"
---

```python
print('Hello')
```
"""
        skill_type = registry.detect_skill_type(skill_content)
        assert skill_type == 'python'

    def test_mixed_python_npm_skill_support(self, db_session):
        """Test skill with both Python and npm packages."""
        registry = SkillRegistryService(db_session)

        skill_content = """---
name: "Hybrid Skill"
packages:
  - requests==2.31.0
node_packages:
  - lodash@4.17.21
package_manager: npm
---

This skill uses both Python and npm.
"""
        skill_type = registry.detect_skill_type(skill_content)
        # node_packages takes priority
        assert skill_type == 'npm'


# End-to-End Tests

class TestEndToEndNpmSkillWorkflow:
    """Test end-to-end npm skill workflow."""

    @patch('core.npm_package_installer.NpmPackageInstaller')
    @patch('core.npm_script_analyzer.NpmScriptAnalyzer')
    @patch('core.package_governance_service.PackageGovernanceService')
    def test_full_npm_skill_workflow(
        self, mock_governance_class, mock_script_analyzer_class, mock_installer_class, db_session
    ):
        """Test full npm skill workflow: import -> install -> execute."""
        registry = SkillRegistryService(db_session)

        # Mock governance
        mock_governance = Mock()
        mock_governance.check_package_permission.return_value = {
            "allowed": True,
            "reason": ""
        }
        mock_governance_class.return_value = mock_governance

        # Mock script analyzer
        mock_script_analyzer = Mock()
        mock_script_analyzer.analyze_package_scripts.return_value = {
            "malicious": False,
            "warnings": []
        }
        mock_script_analyzer_class.return_value = mock_script_analyzer

        # Mock installer
        mock_installer = Mock()
        mock_installer.install_packages.return_value = {
            "success": True,
            "image_tag": "atom-npm-skill:web-scraper-v1",
            "vulnerabilities": []
        }
        mock_installer.execute_with_packages.return_value = "Scraped successfully"
        mock_installer_class.return_value = mock_installer

        # Mock audit service
        with patch('core.audit_service.audit_service') as mock_audit:
            mock_audit.create_package_audit = Mock()

            # Import skill
            skill_content = """---
name: "Web Scraper"
node_packages:
  - axios@^1.6.0
package_manager: npm
---

```javascript
const axios = require('axios');
module.exports = { execute: async (q) => await axios.get(q) };
```
"""
            import_result = registry.import_skill(
                source="raw_content",
                content=skill_content,
                metadata={"imported_by": "user123"}
            )

            assert "skill_id" in import_result
            assert import_result["skill_name"] == "Web Scraper"
            assert import_result["metadata"]["node_packages"] == ["axios@^1.6.0"]

            print("✓ Full npm skill workflow test passed")

    @patch('core.npm_package_installer.NpmPackageInstaller')
    @patch('core.package_governance_service.PackageGovernanceService')
    def test_npm_skill_with_vulnerabilities_blocked(
        self, mock_governance_class, mock_installer_class, db_session
    ):
        """Test npm skill with vulnerabilities is blocked."""
        registry = SkillRegistryService(db_session)

        # Mock governance to allow
        mock_governance = Mock()
        mock_governance.check_package_permission.return_value = {
            "allowed": True,
            "reason": ""
        }
        mock_governance_class.return_value = mock_governance

        # Mock installer to fail due to vulnerabilities
        mock_installer = Mock()
        mock_installer.install_packages.return_value = {
            "success": False,
            "error": "Vulnerabilities detected during scanning",
            "vulnerabilities": ["CVE-2023-1234"]
        }
        mock_installer_class.return_value = mock_installer

        # Mock audit service
        with patch('core.audit_service.audit_service') as mock_audit:
            mock_audit.create_package_audit = Mock()

            # Mock script analyzer
            with patch('core.npm_script_analyzer.NpmScriptAnalyzer') as mock_script_analyzer_class:
                mock_script_analyzer = Mock()
                mock_script_analyzer.analyze_package_scripts.return_value = {
                    "malicious": False,
                    "warnings": []
                }
                mock_script_analyzer_class.return_value = mock_script_analyzer

                # This should fail due to vulnerabilities
                with pytest.raises(ValueError, match="npm installation failed"):
                    registry._install_npm_dependencies_for_skill(
                        skill_id="vulnerable_skill",
                        node_packages=["vulnerable-package@1.0.0"],
                        package_manager="npm",
                        agent_id="agent123",
                        db=db_session
                    )

                print("✓ npm skill with vulnerabilities blocked test passed")
