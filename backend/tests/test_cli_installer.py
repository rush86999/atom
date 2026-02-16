"""
Tests for Atom OS CLI installer.

OpenClaw Integration Tests:
- pip install atom-os works correctly
- atom-os command is available
- CLI shows helpful status and config
- Host mount confirmation works
"""

import pytest
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch


class TestCLIInstallation:
    """Test pip installation and CLI availability."""

    def test_setup_py_exists(self):
        """setup.py exists with correct configuration."""
        setup_file = Path(__file__).parent.parent / "setup.py"
        assert setup_file.exists()

        content = setup_file.read_text()
        assert 'name="atom-os"' in content
        assert 'entry_points' in content
        assert 'atom-os=cli.main:main_cli' in content

    def test_pyproject_toml_exists(self):
        """pyproject.toml exists with modern packaging."""
        pyproject_file = Path(__file__).parent.parent / "pyproject.toml"
        assert pyproject_file.exists()

        content = pyproject_file.read_text()
        assert '[project.scripts]' in content
        assert 'atom-os = ' in content

    def test_cli_module_exists(self):
        """CLI module exists with main function."""
        cli_file = Path(__file__).parent.parent / "cli" / "main.py"
        assert cli_file.exists()

        content = cli_file.read_text()
        assert 'def main_cli()' in content
        assert 'click.group' in content
        assert '@main_cli.command()' in content


class TestCLICommands:
    """Test CLI command execution."""

    def test_cli_help_command(self):
        """atom-os --help shows help message."""
        result = subprocess.run(
            [sys.executable, "-m", "cli.main", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        assert result.returncode == 0
        assert "Atom OS" in result.stdout
        assert "start" in result.stdout
        assert "status" in result.stdout

    def test_cli_status_command(self):
        """atom-os status shows configuration."""
        result = subprocess.run(
            [sys.executable, "-m", "cli.main", "status"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        assert "Atom OS Status" in result.stdout

    def test_cli_config_command(self):
        """atom-os config shows environment variables."""
        result = subprocess.run(
            [sys.executable, "-m", "cli.main", "config"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        assert result.returncode == 0
        assert "Configuration" in result.stdout
        assert "PORT" in result.stdout
        assert "DATABASE_URL" in result.stdout


class TestHostMountConfirmation:
    """Test host mount interactive confirmation."""

    def test_host_mount_requires_confirmation(self):
        """Host mount requires user confirmation."""
        with patch('click.confirm') as mock_confirm:
            mock_confirm.return_value = False

            # Should raise SystemExit when user declines
            with pytest.raises(SystemExit):
                from cli.main import _confirm_host_mount
                _confirm_host_mount()

            # Verify confirm was called
            assert mock_confirm.called

    def test_host_mount_confirmation_message(self):
        """Confirmation message includes security warnings."""
        with patch('click.echo') as mock_echo:
            with patch('click.confirm') as mock_confirm:
                mock_confirm.return_value = False

                from cli.main import _confirm_host_mount
                try:
                    _confirm_host_mount()
                except SystemExit:
                    pass

            # Verify security warnings were displayed
            calls = [call[0][0] for call in mock_echo.call_args_list]
            security_calls = [call for call in calls if "⚠️" in call or "risk" in call.lower()]
            assert len(security_calls) > 0


class TestDependencyInstallation:
    """Test dependencies are correctly installed."""

    def test_click_available(self):
        """Click framework is available."""
        import click
        assert click.__version__ >= "8.0.0"

    def test_fastapi_available(self):
        """FastAPI is available for import."""
        try:
            from main_api_app import app
            assert app is not None
        except ImportError:
            pytest.fail("FastAPI not available")

    def test_governance_cache_available(self):
        """Governance cache is available."""
        try:
            from core.governance_cache import get_governance_cache
            assert callable(get_governance_cache)
        except ImportError:
            pytest.fail("Governance cache not available")
