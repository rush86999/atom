"""
Command Whitelist Tests - Maturity-level enforcement.

Tests ensure command whitelist enforces maturity-based permission boundaries:
- STUDENT agents: Read commands only (suggest-only, not execute)
- INTERN agents: Read commands (requires approval)
- SUPERVISED agents: Write commands (requires approval)
- AUTONOMOUS agents: All whitelisted commands except blocked

Security Focus:
- 4x4 maturity matrix enforcement
- Command category validation (read/write/delete/blocked)
- Suggest-only flow for lower maturity agents
- Blocked commands for all maturity levels
"""

import pytest
from unittest.mock import MagicMock
from unittest.mock import patch

from core.command_whitelist import (
    validate_command,
    get_command_category,
    get_allowed_commands,
    COMMAND_WHITELIST,
    CommandCategory
)
from core.models import AgentStatus


class TestStudentAgentPermissions:
    """Test STUDENT agent command permissions."""

    def test_student_read_commands_allowed(self):
        """STUDENT can suggest read commands (ls, cat, grep)."""
        result = validate_command("ls /tmp", "STUDENT")

        assert result["valid"] == True
        assert result["category"] == "file_read"
        assert result["maturity_required"] == "STUDENT"

    def test_student_cat_command_allowed(self):
        """STUDENT can suggest cat command."""
        result = validate_command("cat file.txt", "STUDENT")

        assert result["valid"] == True
        assert result["category"] == "file_read"

    def test_student_write_commands_blocked(self):
        """STUDENT cannot write (cp, mv, mkdir)."""
        result = validate_command("cp file1.txt file2.txt", "STUDENT")

        assert result["valid"] == False
        assert result["category"] == "file_write"
        assert "SUPERVISED" in result["maturity_required"]

    def test_student_delete_commands_blocked(self):
        """STUDENT cannot delete (rm)."""
        result = validate_command("rm file.txt", "STUDENT")

        assert result["valid"] == False
        assert result["category"] == "file_delete"
        assert result["maturity_required"] == "AUTONOMOUS"

    def test_student_blocked_commands_blocked(self):
        """STUDENT cannot execute blocked commands (chmod, sudo)."""
        result = validate_command("chmod 777 file.txt", "STUDENT")

        assert result["valid"] == False
        assert result["category"] == "blocked"
        assert result["maturity_required"] == "BLOCKED"


class TestInternAgentPermissions:
    """Test INTERN agent command permissions."""

    def test_intern_read_commands_allowed(self):
        """INTERN can suggest read commands."""
        result = validate_command("ls /tmp", "INTERN")

        assert result["valid"] == True
        assert result["category"] == "file_read"

    def test_intern_write_commands_blocked(self):
        """INTERN cannot write without approval."""
        result = validate_command("cp file1.txt file2.txt", "INTERN")

        assert result["valid"] == False
        assert result["category"] == "file_write"
        assert "SUPERVISED" in result["maturity_required"]

    def test_intern_delete_commands_blocked(self):
        """INTERN cannot delete."""
        result = validate_command("rm file.txt", "INTERN")

        assert result["valid"] == False
        assert result["maturity_required"] == "AUTONOMOUS"


class TestSupervisedAgentPermissions:
    """Test SUPERVISED agent command permissions."""

    def test_supervised_read_commands_allowed(self):
        """SUPERVISED can execute read commands."""
        result = validate_command("ls /tmp", "SUPERVISED")

        assert result["valid"] == True
        assert result["category"] == "file_read"

    def test_supervised_write_commands_allowed(self):
        """SUPERVISED can write with approval."""
        result = validate_command("cp file1.txt file2.txt", "SUPERVISED")

        assert result["valid"] == True
        assert result["category"] == "file_write"
        assert result["maturity_required"] == "SUPERVISED"

    def test_supervised_delete_commands_blocked(self):
        """SUPERVISED cannot delete."""
        result = validate_command("rm file.txt", "SUPERVISED")

        assert result["valid"] == False
        assert result["maturity_required"] == "AUTONOMOUS"


class TestAutonomousAgentPermissions:
    """Test AUTONOMOUS agent command permissions."""

    def test_autonomous_read_auto_execute(self):
        """AUTONOMOUS can auto-execute read commands."""
        result = validate_command("ls /tmp", "AUTONOMOUS")

        assert result["valid"] == True
        assert result["category"] == "file_read"
        assert result["maturity_required"] == "AUTONOMOUS"

    def test_autonomous_write_auto_execute(self):
        """AUTONOMOUS can auto-execute write commands."""
        result = validate_command("cp file1.txt file2.txt", "AUTONOMOUS")

        assert result["valid"] == True
        assert result["category"] == "file_write"

    def test_autonomous_delete_auto_execute(self):
        """AUTONOMOUS can auto-execute delete in allowed dirs."""
        result = validate_command("rm file.txt", "AUTONOMOUS")

        assert result["valid"] == True
        assert result["category"] == "file_delete"
        assert result["maturity_required"] == "AUTONOMOUS"

    def test_autonomous_build_tools_allowed(self):
        """AUTONOMOUS can use build tools."""
        result = validate_command("make build", "AUTONOMOUS")

        assert result["valid"] == True
        assert result["category"] == "build_tools"

    def test_autonomous_dev_ops_allowed(self):
        """AUTONOMOUS can use dev ops tools."""
        result = validate_command("git status", "AUTONOMOUS")

        assert result["valid"] == True
        assert result["category"] == "dev_ops"


class TestBlockedCommands:
    """Test blocked commands for all maturity levels."""

    @pytest.mark.parametrize("command", [
        "chmod 777 file.txt",
        "chown user file.txt",
        "kill 1234",
        "sudo ls",
        "reboot",
        "shutdown -h now",
        "iptables -L",
        "usermod -aG group user"
    ])
    @pytest.mark.parametrize("maturity", ["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"])
    def test_blocked_commands_all_levels(self, command, maturity):
        """Blocked commands should be blocked for all maturity levels."""
        result = validate_command(command, maturity)

        assert result["valid"] == False
        assert result["category"] == "blocked"
        assert result["maturity_required"] == "BLOCKED"


class TestCommandCategories:
    """Test command category classification."""

    def test_file_read_commands(self):
        """Verify file_read command category."""
        commands = ["ls", "cat", "head", "tail", "grep", "find", "wc", "pwd"]

        for cmd in commands:
            category = get_command_category(f"{cmd} /tmp")
            assert category == CommandCategory.FILE_READ

    def test_file_write_commands(self):
        """Verify file_write command category."""
        commands = ["cp", "mv", "mkdir", "touch"]

        for cmd in commands:
            category = get_command_category(f"{cmd} file.txt")
            assert category == CommandCategory.FILE_WRITE

    def test_file_delete_commands(self):
        """Verify file_delete command category."""
        category = get_command_category("rm file.txt")
        assert category == CommandCategory.FILE_DELETE

    def test_build_tools_commands(self):
        """Verify build_tools command category."""
        commands = ["make", "npm", "pip", "python3", "node"]

        for cmd in commands:
            category = get_command_category(f"{cmd} build")
            assert category == CommandCategory.BUILD_TOOLS

    def test_dev_ops_commands(self):
        """Verify dev_ops command category."""
        commands = ["git", "docker", "kubectl", "terraform", "ansible"]

        for cmd in commands:
            category = get_command_category(f"{cmd} status")
            assert category == CommandCategory.DEV_OPS

    def test_network_commands(self):
        """Verify network command category."""
        commands = ["curl", "wget", "ping", "nslookup", "dig", "netstat"]

        for cmd in commands:
            category = get_command_category(f"{cmd} example.com")
            assert category == CommandCategory.NETWORK


class TestAllowedCommandsByMaturity:
    """Test get_allowed_commands function."""

    def test_student_allowed_commands(self):
        """STUDENT allowed commands should be read-only."""
        commands = get_allowed_commands("STUDENT")

        # Should include read commands
        assert "ls" in commands
        assert "cat" in commands
        assert "grep" in commands

        # Should NOT include write/delete commands
        assert "cp" not in commands
        assert "rm" not in commands

    def test_autonomous_allowed_commands(self):
        """AUTONOMOUS allowed commands should include all categories."""
        commands = get_allowed_commands("AUTONOMOUS")

        # Should include read, write, delete, build, dev_ops, network
        assert "ls" in commands
        assert "cp" in commands
        assert "rm" in commands
        assert "make" in commands
        assert "git" in commands
        assert "curl" in commands

        # Should NOT include blocked commands
        assert "chmod" not in commands
        assert "sudo" not in commands


class TestParameterizedMaturityMatrix:
    """Test 4x4 maturity matrix using parameterized tests."""

    @pytest.mark.parametrize("maturity,command,expected_valid,expected_category", [
        # STUDENT tests
        ("STUDENT", "ls /tmp", True, "file_read"),
        ("STUDENT", "cat file.txt", True, "file_read"),
        ("STUDENT", "cp a b", False, "file_write"),
        ("STUDENT", "rm file.txt", False, "file_delete"),

        # INTERN tests
        ("INTERN", "ls /tmp", True, "file_read"),
        ("INTERN", "grep pattern file", True, "file_read"),
        ("INTERN", "cp a b", False, "file_write"),
        ("INTERN", "rm file.txt", False, "file_delete"),

        # SUPERVISED tests
        ("SUPERVISED", "ls /tmp", True, "file_read"),
        ("SUPERVISED", "cp a b", True, "file_write"),
        ("SUPERVISED", "mkdir dir", True, "file_write"),
        ("SUPERVISED", "rm file.txt", False, "file_delete"),

        # AUTONOMOUS tests
        ("AUTONOMOUS", "ls /tmp", True, "file_read"),
        ("AUTONOMOUS", "cp a b", True, "file_write"),
        ("AUTONOMOUS", "rm file.txt", True, "file_delete"),
        ("AUTONOMOUS", "make build", True, "build_tools"),
    ])
    def test_maturity_permissions(self, maturity, command, expected_valid, expected_category):
        """Test maturity-based command permissions."""
        result = validate_command(command, maturity)

        assert result["valid"] == expected_valid
        assert result["category"] == expected_category


class TestInvalidCommands:
    """Test invalid commands not in whitelist."""

    def test_non_whitelisted_command(self):
        """Commands not in any whitelist should be invalid."""
        result = validate_command("dangerous-command --arg", "AUTONOMOUS")

        assert result["valid"] == False
        assert result["category"] is None
        assert "not found in any whitelist" in result["reason"]

    def test_empty_command(self):
        """Empty command should be invalid."""
        result = validate_command("", "AUTONOMOUS")

        assert result["valid"] == False
        assert result["category"] is None
        assert "Empty command" in result["reason"]


class TestMaturityUpgradeThresholds:
    """Test maturity upgrade thresholds."""

    def test_command_requires_supervised(self):
        """Commands requiring SUPERVISED maturity."""
        result = validate_command("cp file1 file2", "STUDENT")

        assert result["valid"] == False
        assert "SUPERVISED" in result["maturity_required"]

    def test_command_requires_autonomous(self):
        """Commands requiring AUTONOMOUS maturity."""
        result = validate_command("rm file.txt", "SUPERVISED")

        assert result["valid"] == False
        assert result["maturity_required"] == "AUTONOMOUS"

    def test_command_blocked_all_levels(self):
        """Commands blocked for all maturity levels."""
        result = validate_command("chmod 777 file", "AUTONOMOUS")

        assert result["valid"] == False
        assert result["maturity_required"] == "BLOCKED"
