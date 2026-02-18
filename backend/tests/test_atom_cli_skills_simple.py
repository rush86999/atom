"""
Simple test suite for Atom CLI skills - focused on core functionality.

Validates CLI skill parsing and subprocess wrapper functionality.
"""

import pytest
import tempfile
from pathlib import Path
from typing import Dict, Any

from core.skill_parser import SkillParser
from tools.atom_cli_skill_wrapper import (
    execute_atom_cli_command,
    is_daemon_running,
    get_daemon_pid,
    wait_for_daemon_ready,
    mock_daemon_response,
    build_command_args
)
from unittest.mock import patch, MagicMock


class TestAtomCliSkillParsing:
    """Test parsing of Atom CLI SKILL.md files."""

    @pytest.fixture
    def skill_parser(self):
        """SkillParser instance for testing."""
        return SkillParser()

    @pytest.fixture
    def cli_skill_dir(self):
        """Directory containing CLI skill files."""
        return Path(__file__).parent.parent / "skills/atom-cli"

    def test_parse_atom_daemon_skill(self, skill_parser, cli_skill_dir):
        """Verify atom-daemon.md parses with AUTONOMOUS maturity."""
        skill_file = cli_skill_dir / "atom-daemon.md"

        # Verify file exists
        assert skill_file.exists(), "atom-daemon.md file missing"

        # Parse the skill
        metadata, body = skill_parser.parse_skill_file(str(skill_file))

        # Verify parsing succeeded
        assert metadata is not None, "Skill parsing returned None metadata"
        assert body is not None, "Skill parsing returned None body"

        # Verify skill metadata
        assert metadata["name"] == "atom-daemon"
        assert "background daemon service" in metadata["description"].lower()
        assert metadata["version"] == "1.0.0"
        assert metadata["author"] == "Atom Team"

        # Verify governance maturity
        governance = metadata.get("governance", {})
        assert governance["maturity_requirement"] == "AUTONOMOUS"
        assert "background services" in governance["reason"].lower()

    def test_parse_atom_status_skill(self, skill_parser, cli_skill_dir):
        """Verify atom-status.md parses with STUDENT maturity."""
        skill_file = cli_skill_dir / "atom-status.md"

        assert skill_file.exists(), "atom-status.md file missing"

        metadata, body = skill_parser.parse_skill_file(str(skill_file))

        assert metadata is not None, "Skill parsing failed"
        assert body is not None, "Skill parsing failed"

        assert metadata["name"] == "atom-status"
        assert "daemon status" in metadata["description"].lower()
        assert metadata["maturity_level"] == "STUDENT"

        governance = metadata.get("governance", {})
        assert governance["maturity_requirement"] == "STUDENT"
        assert "read-only" in governance["reason"].lower()

    def test_parse_atom_config_skill(self, skill_parser, cli_skill_dir):
        """Verify atom-config.md parses with STUDENT maturity."""
        skill_file = cli_skill_dir / "atom-config.md"

        assert skill_file.exists(), "atom-config.md file missing"

        metadata, body = skill_parser.parse_skill_file(str(skill_file))

        assert metadata is not None, "Skill parsing failed"
        assert body is not None, "Skill parsing failed"

        assert metadata["name"] == "atom-config"
        assert "configuration" in metadata["description"].lower()
        assert metadata["maturity_level"] == "STUDENT"

        governance = metadata.get("governance", {})
        assert governance["maturity_requirement"] == "STUDENT"


class TestAtomCliSkillMetadata:
    """Test metadata validation for CLI skills."""

    @pytest.fixture
    def skill_parser(self):
        return SkillParser()

    @pytest.fixture
    def cli_skill_dir(self):
        return Path(__file__).parent.parent / "skills/atom-cli"

    def test_all_skills_have_required_fields(self, skill_parser, cli_skill_dir):
        """Verify all 6 CLI skills have required metadata fields."""
        required_fields = ["name", "description", "version", "author", "tags"]
        skill_files = list(cli_skill_dir.glob("atom-*.md"))

        assert len(skill_files) == 6, f"Expected 6 skill files, found {len(skill_files)}"

        for skill_file in skill_files:
            metadata, body = skill_parser.parse_skill_file(str(skill_file))

            assert metadata is not None, f"Failed to parse {skill_file.name}"
            assert body is not None, f"Failed to parse {skill_file.name}"

            # Check required fields exist
            for field in required_fields:
                assert field in metadata, f"Missing field '{field}' in {skill_file.name}"
                assert metadata[field] is not None, f"Empty field '{field}' in {skill_file.name}"
                assert str(metadata[field]).strip(), f"Blank field '{field}' in {skill_file.name}"

    def test_governance_maturity_requirements(self, skill_parser, cli_skill_dir):
        """Verify governance maturity requirements are properly set."""
        skill_files = list(cli_skill_dir.glob("atom-*.md"))

        for skill_file in skill_files:
            metadata, body = skill_parser.parse_skill_file(str(skill_file))

            assert metadata is not None, f"Failed to parse {skill_file.name}"
            assert body is not None, f"Failed to parse {skill_file.name}"

            # Verify governance section exists and has maturity_requirement
            assert "governance" in metadata, f"Missing governance section in {skill_file.name}"
            assert "maturity_requirement" in metadata["governance"], \
                f"Missing maturity_requirement in {skill_file.name}"
            assert metadata["governance"]["maturity_requirement"] in ["STUDENT", "AUTONOMOUS"], \
                f"Invalid maturity_requirement in {skill_file.name}: {metadata['governance']['maturity_requirement']}"

            # Verify reason is present
            assert "reason" in metadata["governance"], f"Missing reason in {skill_file.name}"
            assert len(metadata["governance"]["reason"]) > 10, f"Reason too short in {skill_file.name}"

    def test_autonomous_skills_count(self, skill_parser, cli_skill_dir):
        """Verify 4 skills require AUTONOMOUS maturity."""
        autonomous_count = 0
        skill_files = list(cli_skill_dir.glob("atom-*.md"))

        for skill_file in skill_files:
            metadata, body = skill_parser.parse_skill_file(str(skill_file))

            assert metadata is not None, f"Failed to parse {skill_file.name}"
            assert body is not None, f"Failed to parse {skill_file.name}"

            governance = metadata.get("governance", {})

            if governance.get("maturity_requirement") == "AUTONOMOUS":
                autonomous_count += 1

        assert autonomous_count == 4, f"Expected 4 AUTONOMOUS skills, found {autonomous_count}"

    def test_student_skills_count(self, skill_parser, cli_skill_dir):
        """Verify 2 skills allow STUDENT maturity."""
        student_count = 0
        skill_files = list(cli_skill_dir.glob("atom-*.md"))

        for skill_file in skill_files:
            metadata, body = skill_parser.parse_skill_file(str(skill_file))

            assert metadata is not None, f"Failed to parse {skill_file.name}"
            assert body is not None, f"Failed to parse {skill_file.name}"

            governance = metadata.get("governance", {})

            if governance.get("maturity_requirement") == "STUDENT":
                student_count += 1

        assert student_count == 2, f"Expected 2 STUDENT skills, found {student_count}"


class TestAtomCliWrapperExecution:
    """Test subprocess wrapper with mocked subprocess execution."""

    def test_execute_status_command(self):
        """Mock subprocess.run for status, verify return format."""
        from tools.atom_cli_skill_wrapper import execute_atom_cli_command

        with patch('subprocess.run') as mock_run:
            mock_result = mock_run.return_value
            mock_result.returncode = 0
            mock_result.stdout = "Status: RUNNING\nPID: 12345"
            mock_result.stderr = ""

            result = execute_atom_cli_command("status")

            # Verify subprocess was called correctly
            mock_run.assert_called_once_with(
                ["atom-os", "status"],
                capture_output=True,
                text=True,
                timeout=30
            )

            # Verify return format
            assert result["success"] is True
            assert result["returncode"] == 0
            assert "Status: RUNNING" in result["stdout"]
            assert result["stderr"] == ""

    def test_execute_command_timeout(self):
        """Mock TimeoutExpired, verify timeout handling."""
        from subprocess import TimeoutExpired
        from tools.atom_cli_skill_wrapper import execute_atom_cli_command

        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = TimeoutExpired("atom-os status", 30)

            result = execute_atom_cli_command("status")

            # Verify timeout handling
            assert result["success"] is False
            assert result["returncode"] == -1
            assert result["stderr"] == "Command timed out after 30 seconds"
            assert result["stdout"] == ""

    def test_execute_command_failure(self):
        """Mock returncode=1, verify success=False."""
        from tools.atom_cli_skill_wrapper import execute_atom_cli_command

        with patch('subprocess.run') as mock_run:
            mock_result = mock_run.return_value
            mock_result.returncode = 1
            mock_result.stdout = ""
            mock_result.stderr = "Daemon already running"

            result = execute_atom_cli_command("daemon")

            # Verify failure handling
            assert result["success"] is False
            assert result["returncode"] == 1
            assert result["stdout"] == ""
            assert result["stderr"] == "Daemon already running"

    def test_execute_command_with_args(self):
        """Verify args passed to subprocess correctly."""
        from tools.atom_cli_skill_wrapper import execute_atom_cli_command

        with patch('subprocess.run') as mock_run:
            mock_result = mock_run.return_value
            mock_result.returncode = 0
            mock_result.stdout = "Success"
            mock_result.stderr = ""

            args = ["--port", "3000", "--dev"]
            result = execute_atom_cli_command("daemon", args)

            # Verify command construction
            mock_run.assert_called_once_with(
                ["atom-os", "daemon", "--port", "3000", "--dev"],
                capture_output=True,
                text=True,
                timeout=30
            )

            assert result["success"] is True

    def test_build_command_args(self):
        """Test build_command_args function."""
        from tools.atom_cli_skill_wrapper import build_command_args

        # Test basic args
        args = build_command_args(port=3000, host="localhost")
        assert args == ["--port", "3000", "--host", "localhost"]

        # Test boolean flags
        args = build_command_args(dev=True, host_mount=False)
        assert args == ["--dev"]

        # Test multiple args
        args = build_command_args(
            port=3000,
            host="0.0.0.0",
            workers=4,
            dev=True,
            foreground=False
        )
        expected = ["--port", "3000", "--host", "0.0.0.0", "--workers", "4", "--dev"]
        assert args == expected

        # Test empty args
        args = build_command_args()
        assert args == []


class TestDaemonHelperFunctions:
    """Test daemon helper functions with mocked subprocess."""

    @pytest.fixture
    def mock_execute_atom_cli_command(self, monkeypatch):
        """Mock execute_atom_cli_command for daemon helpers."""
        from tools.atom_cli_skill_wrapper import execute_atom_cli_command
        from unittest.mock import patch

        with patch('tools.atom_cli_skill_wrapper.execute_atom_cli_command') as mock:
            yield mock

    def test_is_daemon_running(self, mock_execute_atom_cli_command):
        """Parse status output for 'RUNNING' string."""
        from tools.atom_cli_skill_wrapper import is_daemon_running

        # Test running daemon
        mock_execute_atom_cli_command.return_value = {
            "success": True,
            "stdout": "Status: RUNNING\nPID: 12345",
            "stderr": "",
            "returncode": 0
        }

        assert is_daemon_running() is True

        # Test stopped daemon
        mock_execute_atom_cli_command.return_value = {
            "success": True,
            "stdout": "Status: STOPPED",
            "stderr": "",
            "returncode": 0
        }

        assert is_daemon_running() is False

        # Test command failure
        mock_execute_atom_cli_command.return_value = {
            "success": False,
            "stdout": "",
            "stderr": "Command failed",
            "returncode": 1
        }

        assert is_daemon_running() is False

    def test_get_daemon_pid(self, mock_execute_atom_cli_command):
        """Extract PID from status output."""
        from tools.atom_cli_skill_wrapper import get_daemon_pid

        # Test valid PID
        mock_execute_atom_cli_command.return_value = {
            "success": True,
            "stdout": "Status: RUNNING\nPID: 12345\nMemory: 128MB",
            "stderr": "",
            "returncode": 0
        }

        pid = get_daemon_pid()
        assert pid == 12345

        # Test daemon not running
        mock_execute_atom_cli_command.return_value = {
            "success": True,
            "stdout": "Status: STOPPED",
            "stderr": "",
            "returncode": 0
        }

        pid = get_daemon_pid()
        assert pid is None

        # Test malformed output
        mock_execute_atom_cli_command.return_value = {
            "success": True,
            "stdout": "Status: RUNNING\nInvalid PID format",
            "stderr": "",
            "returncode": 0
        }

        pid = get_daemon_pid()
        assert pid is None

    def test_mock_daemon_response(self):
        """Test mock_daemon_response utility function."""
        from tools.atom_cli_skill_wrapper import mock_daemon_response

        # Test successful response
        response = mock_daemon_response("Status: RUNNING", "", 0)
        assert response["success"] is True
        assert response["stdout"] == "Status: RUNNING"
        assert response["stderr"] == ""
        assert response["returncode"] == 0

        # Test error response
        response = mock_daemon_response("", "Connection failed", 1)
        assert response["success"] is False
        assert response["stdout"] == ""
        assert response["stderr"] == "Connection failed"
        assert response["returncode"] == 1


class TestAtomCliSkillCoverage:
    """Verify comprehensive test coverage for CLI skills."""

    def test_all_cli_skills_imported(self):
        """Verify all 6 CLI skill files exist."""
        from pathlib import Path

        cli_skill_dir = Path(__file__).parent.parent / "skills/atom-cli"
        skill_files = list(cli_skill_dir.glob("atom-*.md"))

        assert len(skill_files) == 6, f"Expected 6 CLI skills, found {len(skill_files)}"

        expected_skills = ["atom-daemon", "atom-status", "atom-start", "atom-stop", "atom-execute", "atom-config"]
        actual_skills = [f.stem for f in skill_files]

        for expected in expected_skills:
            assert expected in actual_skills, f"Missing skill: {expected}"

    def test_skill_parsing_completeness(self):
        """Test that all skills parse without errors."""
        from core.skill_parser import SkillParser
        from pathlib import Path

        parser = SkillParser()
        cli_skill_dir = Path(__file__).parent.parent / "skills/atom-cli"
        skill_files = list(cli_skill_dir.glob("atom-*.md"))

        for skill_file in skill_files:
            metadata, body = parser.parse_skill_file(str(skill_file))

            assert metadata is not None, f"Failed to parse {skill_file.name}"
            assert body is not None, f"Failed to parse {skill_file.name}"

            assert metadata["name"] is not None
            assert metadata["description"] is not None
            assert metadata["version"] is not None
            assert metadata["author"] is not None

    def test_governance_maturity_distribution(self):
        """Verify maturity distribution matches expectations."""
        from core.skill_parser import SkillParser
        from pathlib import Path

        parser = SkillParser()
        cli_skill_dir = Path(__file__).parent.parent / "skills/atom-cli"
        skill_files = list(cli_skill_dir.glob("atom-*.md"))

        autonomous_count = 0
        student_count = 0

        for skill_file in skill_files:
            metadata, body = parser.parse_skill_file(str(skill_file))
            governance = metadata.get("governance", {})

            if governance.get("maturity_requirement") == "AUTONOMOUS":
                autonomous_count += 1
            elif governance.get("maturity_requirement") == "STUDENT":
                student_count += 1

        assert autonomous_count == 4, f"Expected 4 AUTONOMOUS skills, got {autonomous_count}"
        assert student_count == 2, f"Expected 2 STUDENT skills, got {student_count}"