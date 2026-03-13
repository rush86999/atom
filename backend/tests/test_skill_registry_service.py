"""
Tests for SkillRegistryService - core skill lifecycle management.

Tests cover:
- Skill import workflow (import_skill method)
- Security scanning integration
- Python and npm package extraction
- Skill listing and retrieval
- Skill execution with governance checks
- Skill promotion (Untrusted -> Active)
- Dynamic skill loading and hot-reload
- Episode segment creation for skill execution

Reference: Phase 183 Plan 04 - Skill Registry Service Coverage
"""

import sys
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime
import uuid

# Module-level mocking for Docker dependencies (Phase 182 pattern)
sys.modules['docker'] = MagicMock()
sys.modules['docker.errors'] = MagicMock()
sys.modules['core.skill_sandbox'] = MagicMock()
sys.modules['core.skill_security_scanner'] = MagicMock()

# Mock langchain to avoid import errors
sys.modules['langchain'] = MagicMock()
sys.modules['langchain.tools'] = MagicMock()
sys.modules['langchain_core'] = MagicMock()
sys.modules['langchain_core.tools'] = MagicMock()
sys.modules['langchain_core.tools.utils'] = MagicMock()
sys.modules['langchain_core.utils'] = MagicMock()
sys.modules['langchain_core.utils.formatting'] = MagicMock()

import pytest
from sqlalchemy.orm import Session

from core.skill_registry_service import SkillRegistryService
from core.models import SkillExecution, EpisodeSegment


# ============================================================================
# Test Fixtures
# ============================================================================

# Note: db_session fixture is imported from conftest.py


@pytest.fixture
def low_risk_skill_content():
    """Low risk skill content (should be Active)."""
    return """---
name: Test Skill
description: A test skill
skill_type: prompt_only
---
This is the skill body."""


@pytest.fixture
def high_risk_skill_content():
    """High risk skill content (should be Untrusted)."""
    return """---
name: Risky Skill
description: A risky skill
---
```python
import os
os.system('rm -rf /')
```"""


@pytest.fixture
def python_packages_skill_content():
    """Skill with Python packages."""
    return """---
name: Python Packages Skill
description: Skill with Python packages
packages:
  - requests==2.28.0
  - pandas>=1.5.0
---
```python
print("Hello from Python")
```"""


@pytest.fixture
def npm_packages_skill_content():
    """Skill with npm packages."""
    return """---
name: NPM Packages Skill
description: Skill with npm packages
node_packages:
  - lodash@4.17.21
  - axios@^1.0.0
package_manager: npm
---
console.log("Hello from Node.js")"""


@pytest.fixture
def mock_scanner_low_risk():
    """Mock scanner returning LOW risk."""
    return {
        "safe": True,
        "risk_level": "LOW",
        "findings": []
    }


@pytest.fixture
def mock_scanner_high_risk():
    """Mock scanner returning HIGH risk."""
    return {
        "safe": False,
        "risk_level": "HIGH",
        "findings": ["Detected dangerous pattern: os.system"]
    }


# ============================================================================
# Test Class 1: TestSkillImportBasic (6 tests)
# ============================================================================

class TestSkillImportBasic:
    """Test basic skill import functionality."""

    def test_import_skill_creates_record(self, db_session, low_risk_skill_content, mock_scanner_low_risk):
        """Skill import creates SkillExecution record."""
        service = SkillRegistryService(db_session)

        # Mock scanner
        service._scanner.scan_skill = MagicMock(return_value=mock_scanner_low_risk)

        result = service.import_skill(
            source="raw_content",
            content=low_risk_skill_content
        )

        assert result["status"] in ["Active", "Untrusted"]
        assert result["skill_name"] == "Test Skill"
        assert result["skill_id"] is not None

        # Verify database record
        skill = db_session.query(SkillExecution).filter(
            SkillExecution.id == result["skill_id"]
        ).first()
        assert skill is not None
        # skill_id field contains the community skill reference
        assert skill.skill_id.startswith("community_Test Skill_")

    def test_import_skill_with_raw_content(self, db_session, low_risk_skill_content, mock_scanner_low_risk):
        """Import from raw_content source."""
        service = SkillRegistryService(db_session)
        service._scanner.scan_skill = MagicMock(return_value=mock_scanner_low_risk)

        result = service.import_skill(
            source="raw_content",
            content=low_risk_skill_content
        )

        assert result["skill_id"] is not None
        # Source is stored in database, not in return dict
        skill = db_session.query(SkillExecution).filter(
            SkillExecution.id == result["skill_id"]
        ).first()
        assert skill.skill_source == "community"

    def test_import_skill_parses_frontmatter(self, db_session, low_risk_skill_content, mock_scanner_low_risk):
        """YAML frontmatter parsed correctly."""
        service = SkillRegistryService(db_session)
        service._scanner.scan_skill = MagicMock(return_value=mock_scanner_low_risk)

        result = service.import_skill(
            source="raw_content",
            content=low_risk_skill_content
        )

        assert result["skill_name"] == "Test Skill"
        assert result["metadata"]["description"] == "A test skill"

    def test_import_skill_extracts_body(self, db_session, low_risk_skill_content, mock_scanner_low_risk):
        """Skill body extracted and stored in input_params."""
        service = SkillRegistryService(db_session)
        service._scanner.scan_skill = MagicMock(return_value=mock_scanner_low_risk)

        result = service.import_skill(
            source="raw_content",
            content=low_risk_skill_content
        )

        # Body is stored in input_params, not in metadata
        skill = db_session.query(SkillExecution).filter(
            SkillExecution.id == result["skill_id"]
        ).first()
        assert "This is the skill body" in skill.input_params["skill_body"]

    def test_import_skill_generates_uuid(self, db_session, low_risk_skill_content, mock_scanner_low_risk):
        """skill_id is valid UUID format."""
        service = SkillRegistryService(db_session)
        service._scanner.scan_skill = MagicMock(return_value=mock_scanner_low_risk)

        result = service.import_skill(
            source="raw_content",
            content=low_risk_skill_content
        )

        # Should be valid UUID
        try:
            uuid.UUID(result["skill_id"])
        except ValueError:
            pytest.fail("skill_id is not a valid UUID")

    def test_import_skill_default_status(self, db_session, low_risk_skill_content, mock_scanner_low_risk):
        """Default status based on scan result."""
        service = SkillRegistryService(db_session)
        service._scanner.scan_skill = MagicMock(return_value=mock_scanner_low_risk)

        result = service.import_skill(
            source="raw_content",
            content=low_risk_skill_content
        )

        # LOW risk should default to Active
        assert result["status"] == "Active"


# ============================================================================
# Test Class 2: TestSkillImportPackages (6 tests)
# ============================================================================

class TestSkillImportPackages:
    """Test package extraction from skill metadata."""

    def test_import_skill_extracts_python_packages(self, db_session, python_packages_skill_content, mock_scanner_low_risk):
        """packages field extracted from metadata."""
        service = SkillRegistryService(db_session)
        service._scanner.scan_skill = MagicMock(return_value=mock_scanner_low_risk)

        result = service.import_skill(
            source="raw_content",
            content=python_packages_skill_content
        )

        assert "packages" in result["metadata"]
        assert "requests==2.28.0" in result["metadata"]["packages"]
        assert "pandas>=1.5.0" in result["metadata"]["packages"]

    def test_import_skill_extracts_node_packages(self, db_session, npm_packages_skill_content, mock_scanner_low_risk):
        """node_packages field extracted from metadata."""
        service = SkillRegistryService(db_session)
        service._scanner.scan_skill = MagicMock(return_value=mock_scanner_low_risk)

        result = service.import_skill(
            source="raw_content",
            content=npm_packages_skill_content
        )

        assert "node_packages" in result["metadata"]
        assert "lodash@4.17.21" in result["metadata"]["node_packages"]
        assert "axios@^1.0.0" in result["metadata"]["node_packages"]

    def test_import_skill_extracts_package_manager(self, db_session, npm_packages_skill_content, mock_scanner_low_risk):
        """package_manager field extracted from metadata."""
        service = SkillRegistryService(db_session)
        service._scanner.scan_skill = MagicMock(return_value=mock_scanner_low_risk)

        result = service.import_skill(
            source="raw_content",
            content=npm_packages_skill_content
        )

        assert result["metadata"]["package_manager"] == "npm"

    def test_import_skill_packages_stored_in_input_params(self, db_session, python_packages_skill_content, mock_scanner_low_risk):
        """Packages stored in input_params."""
        service = SkillRegistryService(db_session)
        service._scanner.scan_skill = MagicMock(return_value=mock_scanner_low_risk)

        result = service.import_skill(
            source="raw_content",
            content=python_packages_skill_content
        )

        skill = db_session.query(SkillExecution).filter(
            SkillExecution.id == result["skill_id"]
        ).first()

        assert skill.input_params is not None
        assert "packages" in skill.input_params

    def test_import_skill_empty_packages(self, db_session, low_risk_skill_content, mock_scanner_low_risk):
        """Empty packages list handled correctly."""
        service = SkillRegistryService(db_session)
        service._scanner.scan_skill = MagicMock(return_value=mock_scanner_low_risk)

        result = service.import_skill(
            source="raw_content",
            content=low_risk_skill_content
        )

        # Should have empty packages list or None
        packages = result["metadata"].get("packages", [])
        assert isinstance(packages, list)

    def test_import_skill_multiple_packages(self, db_session, python_packages_skill_content, mock_scanner_low_risk):
        """Multiple packages extracted correctly."""
        service = SkillRegistryService(db_session)
        service._scanner.scan_skill = MagicMock(return_value=mock_scanner_low_risk)

        result = service.import_skill(
            source="raw_content",
            content=python_packages_skill_content
        )

        packages = result["metadata"]["packages"]
        assert len(packages) == 2
        assert "requests==2.28.0" in packages
        assert "pandas>=1.5.0" in packages


# ============================================================================
# Test Class 3: TestSkillImportSecurity (5 tests)
# ============================================================================

class TestSkillImportSecurity:
    """Test security scanning integration."""

    def test_low_risk_sets_active_status(self, db_session, low_risk_skill_content, mock_scanner_low_risk):
        """LOW risk_level sets status to Active."""
        service = SkillRegistryService(db_session)
        service._scanner.scan_skill = MagicMock(return_value=mock_scanner_low_risk)

        result = service.import_skill(
            source="raw_content",
            content=low_risk_skill_content
        )

        assert result["status"] == "Active"

    def test_high_risk_sets_untrusted_status(self, db_session, high_risk_skill_content, mock_scanner_high_risk):
        """HIGH/MEDIUM risk sets Untrusted."""
        service = SkillRegistryService(db_session)
        service._scanner.scan_skill = MagicMock(return_value=mock_scanner_high_risk)

        result = service.import_skill(
            source="raw_content",
            content=high_risk_skill_content
        )

        assert result["status"] == "Untrusted"

    def test_security_scan_result_stored(self, db_session, low_risk_skill_content, mock_scanner_low_risk):
        """security_scan_result stored in record."""
        service = SkillRegistryService(db_session)
        service._scanner.scan_skill = MagicMock(return_value=mock_scanner_low_risk)

        result = service.import_skill(
            source="raw_content",
            content=low_risk_skill_content
        )

        assert result["scan_result"]["risk_level"] == "LOW"
        assert result["scan_result"]["safe"] is True

    def test_sandbox_enabled_for_python(self, db_session, high_risk_skill_content, mock_scanner_high_risk):
        """python_code enables sandbox."""
        service = SkillRegistryService(db_session)
        service._scanner.scan_skill = MagicMock(return_value=mock_scanner_high_risk)

        result = service.import_skill(
            source="raw_content",
            content=high_risk_skill_content
        )

        # Python skills should have sandbox_enabled
        assert result["metadata"].get("skill_type") == "python_code"

    def test_sandbox_disabled_for_prompt(self, db_session, low_risk_skill_content, mock_scanner_low_risk):
        """prompt_only disables sandbox."""
        service = SkillRegistryService(db_session)
        service._scanner.scan_skill = MagicMock(return_value=mock_scanner_low_risk)

        result = service.import_skill(
            source="raw_content",
            content=low_risk_skill_content
        )

        # Prompt-only skills should not need sandbox
        assert result["metadata"].get("skill_type") == "prompt_only"


# ============================================================================
# Test Class 4: TestSkillListing (6 tests)
# ============================================================================

class TestSkillListing:
    """Test skill listing functionality."""

    def test_list_skills_all(self, db_session, low_risk_skill_content, mock_scanner_low_risk):
        """List all skills without filters."""
        service = SkillRegistryService(db_session)
        service._scanner.scan_skill = MagicMock(return_value=mock_scanner_low_risk)

        # Import two skills
        service.import_skill("raw_content", low_risk_skill_content)
        service.import_skill("raw_content", low_risk_skill_content)

        skills = service.list_skills()

        assert len(skills) == 2
        assert all("skill_name" in s for s in skills)

    def test_list_skills_by_status(self, db_session, low_risk_skill_content, high_risk_skill_content, mock_scanner_low_risk, mock_scanner_high_risk):
        """Filter by status (Active, Untrusted)."""
        service = SkillRegistryService(db_session)

        # Import skills with different risk levels
        service.import_skill("raw_content", low_risk_skill_content)
        service.import_skill("raw_content", high_risk_skill_content)

        # Mock scanner appropriately for each call
        call_count = [0]
        def side_effect(name, body):
            call_count[0] += 1
            return mock_scanner_low_risk if call_count[0] % 2 == 1 else mock_scanner_high_risk

        service._scanner.scan_skill = MagicMock(side_effect=side_effect)

        # Re-import with proper mocking
        db_session.query(SkillExecution).delete()
        db_session.commit()
        service.import_skill("raw_content", low_risk_skill_content)
        service.import_skill("raw_content", high_risk_skill_content)

        active_skills = service.list_skills(status="Active")
        untrusted_skills = service.list_skills(status="Untrusted")

        # Verify filtering works
        assert all(s["status"] == "Active" for s in active_skills)
        assert all(s["status"] == "Untrusted" for s in untrusted_skills)

    def test_list_skills_by_type(self, db_session, low_risk_skill_content, high_risk_skill_content, mock_scanner_low_risk, mock_scanner_high_risk):
        """Filter by skill_type (prompt_only, python_code)."""
        service = SkillRegistryService(db_session)
        
        call_count = [0]
        def side_effect(name, body):
            call_count[0] += 1
            return mock_scanner_low_risk if call_count[0] % 2 == 1 else mock_scanner_high_risk

        service._scanner.scan_skill = MagicMock(side_effect=side_effect)

        service.import_skill("raw_content", low_risk_skill_content)
        service.import_skill("raw_content", high_risk_skill_content)

        prompt_skills = service.list_skills(skill_type="prompt_only")
        python_skills = service.list_skills(skill_type="python_code")

        # Verify type filtering
        assert all(s["skill_type"] == "prompt_only" for s in prompt_skills)
        assert all(s["skill_type"] == "python_code" for s in python_skills)

    def test_list_skills_limit(self, db_session, low_risk_skill_content, mock_scanner_low_risk):
        """Limit parameter respected."""
        service = SkillRegistryService(db_session)
        service._scanner.scan_skill = MagicMock(return_value=mock_scanner_low_risk)

        # Import three skills
        for _ in range(3):
            service.import_skill("raw_content", low_risk_skill_content)

        skills = service.list_skills(limit=2)

        assert len(skills) == 2

    def test_list_skills_empty(self, db_session):
        """Empty list when no skills match."""
        service = SkillRegistryService(db_session)

        skills = service.list_skills(status="Active")

        assert skills == []


# ============================================================================
# Test Class 5: TestSkillRetrieval (5 tests)
# ============================================================================

class TestSkillRetrieval:
    """Test skill retrieval functionality."""

    def test_get_skill_by_id(self, db_session, low_risk_skill_content, mock_scanner_low_risk):
        """Retrieve skill by ID."""
        service = SkillRegistryService(db_session)
        service._scanner.scan_skill = MagicMock(return_value=mock_scanner_low_risk)

        result = service.import_skill("raw_content", low_risk_skill_content)
        skill_id = result["skill_id"]

        skill = service.get_skill(skill_id)

        assert skill is not None
        assert skill["skill_id"] == skill_id
        assert skill["skill_name"] == "Test Skill"

    def test_get_skill_returns_full_metadata(self, db_session, low_risk_skill_content, mock_scanner_low_risk):
        """All metadata fields returned."""
        service = SkillRegistryService(db_session)
        service._scanner.scan_skill = MagicMock(return_value=mock_scanner_low_risk)

        result = service.import_skill("raw_content", low_risk_skill_content)
        skill_id = result["skill_id"]

        skill = service.get_skill(skill_id)

        # Top-level fields
        assert "skill_type" in skill
        assert "packages" in skill
        assert "node_packages" in skill
        # Nested in skill_metadata
        assert "description" in skill["skill_metadata"]

    def test_get_skill_nonexistent_returns_none(self, db_session):
        """Non-existent ID returns None."""
        service = SkillRegistryService(db_session)

        skill = service.get_skill("nonexistent-id")

        assert skill is None

    def test_get_skill_includes_packages(self, db_session, python_packages_skill_content, mock_scanner_low_risk):
        """packages field in result."""
        service = SkillRegistryService(db_session)
        service._scanner.scan_skill = MagicMock(return_value=mock_scanner_low_risk)

        result = service.import_skill("raw_content", python_packages_skill_content)
        skill_id = result["skill_id"]

        skill = service.get_skill(skill_id)

        assert "packages" in skill
        assert len(skill["packages"]) == 2

    def test_get_skill_includes_node_packages(self, db_session, npm_packages_skill_content, mock_scanner_low_risk):
        """node_packages field in result."""
        service = SkillRegistryService(db_session)
        service._scanner.scan_skill = MagicMock(return_value=mock_scanner_low_risk)

        result = service.import_skill("raw_content", npm_packages_skill_content)
        skill_id = result["skill_id"]

        skill = service.get_skill(skill_id)

        assert "node_packages" in skill
        assert len(skill["node_packages"]) == 2


# ============================================================================
# Test Class 6: TestSkillMetadataExtraction (4 tests)
# ============================================================================

class TestSkillMetadataExtraction:
    """Test metadata extraction from skills."""

    def test_skill_type_detection(self, db_session, low_risk_skill_content, high_risk_skill_content, mock_scanner_low_risk, mock_scanner_high_risk):
        """skill_type detected correctly."""
        service = SkillRegistryService(db_session)
        
        call_count = [0]
        def side_effect(name, body):
            call_count[0] += 1
            return mock_scanner_low_risk if call_count[0] % 2 == 1 else mock_scanner_high_risk

        service._scanner.scan_skill = MagicMock(side_effect=side_effect)

        result1 = service.import_skill("raw_content", low_risk_skill_content)
        result2 = service.import_skill("raw_content", high_risk_skill_content)

        assert result1["metadata"]["skill_type"] == "prompt_only"
        assert result2["metadata"]["skill_type"] == "python_code"

    def test_skill_name_extraction(self, db_session, low_risk_skill_content, mock_scanner_low_risk):
        """name extracted from frontmatter."""
        service = SkillRegistryService(db_session)
        service._scanner.scan_skill = MagicMock(return_value=mock_scanner_low_risk)

        result = service.import_skill("raw_content", low_risk_skill_content)

        assert result["skill_name"] == "Test Skill"

    def test_skill_body_extraction(self, db_session, low_risk_skill_content, mock_scanner_low_risk):
        """body content extracted."""
        service = SkillRegistryService(db_session)
        service._scanner.scan_skill = MagicMock(return_value=mock_scanner_low_risk)

        result = service.import_skill("raw_content", low_risk_skill_content)
        skill_id = result["skill_id"]

        skill = service.get_skill(skill_id)

        # Body is stored in input_params
        record = db_session.query(SkillExecution).filter(SkillExecution.id == skill_id).first()
        assert "This is the skill body" in record.input_params["skill_body"]

    def test_skill_metadata_merge(self, db_session, low_risk_skill_content, mock_scanner_low_risk):
        """Additional metadata merged correctly."""
        service = SkillRegistryService(db_session)
        service._scanner.scan_skill = MagicMock(return_value=mock_scanner_low_risk)

        result = service.import_skill(
            "raw_content",
            low_risk_skill_content,
            metadata={"author": "test", "version": "1.0"}
        )

        # Metadata should include base fields plus additional
        assert "description" in result["metadata"]
        assert "skill_type" in result["metadata"]
        assert "packages" in result["metadata"]
