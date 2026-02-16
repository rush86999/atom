---
phase: 13-openclaw-integration
plan: 03
type: execute
wave: 2
depends_on: []
files_modified:
  - backend/cli/__init__.py
  - backend/cli/main.py
  - backend/setup.py
  - backend/pyproject.toml
  - README.md
  - backend/tests/test_cli_installer.py
autonomous: true

must_haves:
  truths:
    - User can install Atom with `pip install atom-os`
    - User can start Atom with `atom-os` command
    - CLI provides helpful startup messages and warnings
    - CLI option enables host filesystem mount with confirmation
    - Installation works on Python 3.11+
    - Package includes all necessary dependencies
    - CLI integrates with existing main_api_app.py
    - Installation warns about security implications
  artifacts:
    - path: backend/setup.py
      provides: Python package configuration
      contains: "setup(", "entry_points", "console_scripts"
    - path: backend/cli/main.py
      provides: CLI entry point with Click framework
      min_lines: 100
      exports: ["main_cli"]
    - path: backend/pyproject.toml
      provides: Modern Python packaging metadata
      contains: "[project.console_scripts]"
  key_links:
    - from: "backend/setup.py"
      to: "backend/cli/main.py"
      via: "console_scripts entry point"
      pattern: "console_scripts.*atom-os"
    - from: "backend/cli/main.py"
      to: "backend/main_api_app.py"
      via: "Import and initialize FastAPI app"
      pattern: "from.*main_api_app.*import.*app"
---

<objective>
Create simplified installer for Atom - "pip install atom-os".

OpenClaw's viral feature: Single-line installer (`npm install -g openclaw`). Atom's twist: Full-featured Atom with optional host mount, security warnings, governance-first defaults.

Purpose: Reduce friction for "vibe coder" entry while maintaining enterprise features
Output: pip-installable package with `atom-os` CLI command
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
@/Users/rushiparikh/.claude/get-shit-done/references/checkpoints.md
@/Users/rushikhar/.claude/get-shit-done/references/tdd.md
</execution_context>

<context>
@.planning/phases/13-openclaw-integration/13-RESEARCH.md
@.planning/ROADMAP.md
@.planning/STATE.md

# Existing implementations
@backend/main_api_app.py
@backend/docker/docker-compose.yml
@backend/requirements.txt
</context>

<tasks>

<task type="auto">
  <name>Create CLI entry point with Click</name>
  <files>backend/cli/main.py</files>
  <action>
Create backend/cli/main.py (150-200 lines):

```python
#!/usr/bin/env python3
"""
Atom OS CLI - Command-line interface for Atom AI automation platform.

OpenClaw Integration: Single-command installer for "vibe coder" entry.
Full-featured Atom with optional host mount (governance-first).

Usage:
    pip install atom-os
    atom-os --help
"""

import os
import sys
import click
import logging
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version="0.1.0")
def main_cli():
    """
    Atom OS - AI-powered business automation platform.

    Governance-first architecture with multi-agent system.
    """
    pass


@main_cli.command()
@click.option('--port', default=8000, help='Port for web server')
@click.option('--host', default='0.0.0.0', help='Host to bind to')
@click.option('--workers', default=1, help='Number of worker processes')
@click.option('--host-mount', is_flag=True, help='Enable host filesystem mount (Docker)')
@click.option('--dev', is_flag=True, help='Enable development mode (auto-reload)')
def start(port: int, host: str, workers: int, host_mount: bool, dev: bool):
    """
    Start Atom OS server.

    Starts FastAPI server with optional host filesystem mount.

    **Host Mount Warning:**
    This gives containers write access to host directories.
    Only enable after reviewing governance protections:
      - AUTONOMOUS maturity gate required for shell access
      - Command whitelist (ls, cat, grep, git, npm, etc.)
      - Blocked commands (rm, mv, chmod, kill, sudo, etc.)
      - 5-minute timeout enforcement
      - Full audit trail to ShellSession table

    **Examples:**
        atom-os                                    # Start on localhost:8000
        atom-os --port 3000 --dev                # Development mode with reload
        atom-os --host-mount                     # With host mount (requires confirmation)
    """
    # Import after CLI to avoid slow startup
    from main_api_app import app

    if host_mount:
        _confirm_host_mount()
        os.environ["ATOM_HOST_MOUNT_ENABLED"] = "true"

        # Configure host mount directories
        current_user = os.getenv("USER", "unknown")
        os.environ.setdefault(
            "ATOM_HOST_MOUNT_DIRS",
            f"/tmp:/Users/{current_user}/projects:/Users/{current_user}/Desktop:/Users/{current_user}/Documents"
        )

        click.echo(click.style("⚠️  Host filesystem mount ENABLED", fg="yellow", bold=True))
        click.echo("Governance protections active:")
        click.echo("  ✓ AUTONOMOUS maturity gate")
        click.echo("  ✓ Command whitelist")
        click.echo("  ✓ Blocked commands")
        click.echo("  ✓ 5-minute timeout")
        click.echo("  ✓ Audit trail")
        click.echo("")

    # Start server
    import uvicorn

    click.echo(click.style("🚀 Starting Atom OS...", fg="green", bold=True))
    click.echo(f"  Host: {host}")
    click.echo(f"  Port: {port}")
    click.echo(f"  Workers: {workers}")
    click.echo(f"  Dev mode: {dev}")
    click.echo(f"  Host mount: {host_mount}")
    click.echo("")
    click.echo(f"  Dashboard: http://{host}:{port}")
    click.echo(f"  API docs: http://{host}:{port}/docs")
    click.echo("")

    if dev:
        # Development mode with auto-reload
        uvicorn.run(
            "main_api_app:app",
            host=host,
            port=port,
            reload=True,
            log_level="info"
        )
    else:
        # Production mode
        uvicorn.run(
            "main_api_app:app",
            host=host,
            port=port,
            workers=workers,
            log_level="info",
            access_log=True
        )


@main_cli.command()
def status():
    """Show Atom OS status and configuration."""
    # Import after CLI to avoid slow startup
    from main_api_app import app
    from core.governance_cache import get_governance_cache

    click.echo(click.style("Atom OS Status", bold=True))
    click.echo("=" * 40)

    # Check host mount
    host_mount_enabled = os.getenv("ATOM_HOST_MOUNT_ENABLED", "false").lower() == "true"
    click.echo(f"Host mount: {click.style('ENABLED' if host_mount_enabled else 'disabled', fg='yellow' if host_mount_enabled else 'dim')}")

    # Check governance cache
    try:
        cache = get_governance_cache()
        click.echo(f"Governance cache: {click.style('connected', fg='green')}")
    except Exception as e:
        click.echo(f"Governance cache: {click.style('disconnected', fg='red')} ({e})")

    # Check database
    try:
        from core.models import engine
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        click.echo(f"Database: {click.style('connected', fg='green')}")
    except Exception as e:
        click.echo(f"Database: {click.style('disconnected', fg='red')} ({e})")

    # Show configuration
    click.echo("")
    click.echo("Environment:")
    port = os.getenv("PORT", "8000")
    click.echo(f"  PORT: {port}")

    if host_mount_enabled:
        mount_dirs = os.getenv("ATOM_HOST_MOUNT_DIRS", "not configured")
        click.echo(f"  Host mount dirs: {mount_dirs}")


@main_cli.command()
def config():
    """Show configuration details and environment variables."""
    click.echo(click.style("Atom OS Configuration", bold=True))
    click.echo("=" * 40)
    click.echo("")
    click.echo("Environment Variables:")
    click.echo("")
    click.echo("Server:")
    click.echo("  PORT              - Server port (default: 8000)")
    click.echo("  HOST             - Server host (default: 0.0.0.0)")
    click.echo("  WORKERS          - Worker processes (default: 1)")
    click.echo("")
    click.echo("Host Mount (SECURITY WARNING):")
    click.echo("  ATOM_HOST_MOUNT_ENABLED  - Enable host filesystem mount")
    click.echo("  ATOM_HOST_MOUNT_DIRS     - Allowed directories (colon-separated)")
    click.echo("")
    click.echo("Database:")
    click.echo("  DATABASE_URL      - Database connection string")
    click.echo("")
    click.echo("LLM Providers:")
    click.echo("  OPENAI_API_KEY    - OpenAI API key")
    click.echo("  ANTHROPIC_API_KEY - Anthropic API key")
    click.echo("  DEEPSEEK_API_KEY  - DeepSeek API key")
    click.echo("")
    click.echo("See .env file for full configuration.")


def _confirm_host_mount():
    """Interactive confirmation for host mount."""
    click.echo(click.style("⚠️  HOST FILESYSTEM MOUNT", fg="yellow", bold=True))
    click.echo("")
    click.echo("You are about to enable host filesystem access for Atom containers.")
    click.echo("")
    click.echo("This gives containers WRITE access to host directories.")
    click.echo("")
    click.echo("Governance protections in place:")
    click.echo("  ✓ AUTONOMOUS maturity gate required for shell access")
    click.echo("  ✓ Command whitelist (ls, cat, grep, git, npm, etc.)")
    click.echo("  ✓ Blocked commands (rm, mv, chmod, kill, sudo, etc.)")
    click.echo("  ✓ 5-minute timeout enforcement")
    click_echo("  ✓ Full audit trail to ShellSession table")
    click.echo("")
    click.echo("However, this STILL carries risk:")
    click.echo("  - Bugs in governance code could bypass protections")
    click.echo("  - Compromised AUTONOMOUS agent has shell access")
    click.echo("  - Docker escape vulnerabilities could be exploited")
    click.echo("")

    if not click.confirm("Do you understand the risks and want to continue?"):
        click.echo("Host mount cancelled.")
        raise SystemExit(1)

    click.echo("")
    click.echo("✓ Host mount confirmed")


if __name__ == "__main__":
    main_cli()
```

Follow Atom patterns:
- Click framework for CLI (better UX than argparse)
- Type hints and docstrings
- Security warnings for dangerous features
- Helpful startup messages
  </action>
  <verify>
```bash
# Verify CLI created
test -f backend/cli/main.py
grep -n "click.group" backend/cli/main.py
grep -n "def start" backend/cli/main.py
grep -n "def status" backend/cli/main.py
```
  </verify>
  <done>
CLI entry point created with:
- Click framework for CLI commands
- atom-os start command with options (port, host, workers, host-mount, dev)
- atom-os status command for system status
- atom-os config command for environment variables
- Host mount confirmation with security warnings
- Helpful startup messages and colors
  </done>
</task>

<task type="auto">
  <name>Create setup.py for pip packaging</name>
  <files>backend/setup.py</files>
  <action>
Create backend/setup.py (100-150 lines):

```python
"""
Setup configuration for pip installable Atom OS package.

OpenClaw Integration: Single-command installer ("pip install atom-os").
Full-featured Atom with governance-first architecture.
"""

from setuptools import setup, find_packages
from pathlib import Path
import os

# Read README for long description
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text() if readme_file.exists() else ""

# Read requirements
requirements_file = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_file.exists():
    with open(requirements_file) as "r" as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

setup(
    name="atom-os",
    version="0.1.0",
    description="AI-powered business automation platform with multi-agent governance",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Atom Platform",
    author_email="contact@atom-platform.dev",
    url="https://github.com/rush86999/atom",
    project_urls={
        "Bug Tracker": "https://github.com/rush86999/atom/issues",
        "Documentation": "https://github.com/rush86999/atom/tree/main/docs",
        "Source Code": "https://github.com/rush86999/atom",
    },

    packages=find_packages(exclude=["tests.*", "tests", "*.tests", "*.tests.*"]),
    include_package_data=True,

    # Python version requirement
    python_requires=">=3.11",

    # Dependencies
    install_requires=requirements + [
        # CLI dependencies
        "click>=8.0.0",

        # Core dependencies (from requirements.txt, ensuring minimum versions)
        "fastapi>=0.100.0",
        "uvicorn[standard]>=0.20.0",
        "sqlalchemy>=2.0.0",
        "pydantic>=2.0.0",
        "python-multipart>=0.0.5",
        "python-jose[cryptography]>=3.3.0",
        "passlib[bcrypt]>=1.7.4",
        "python-dotenv>=1.0.0",
        "alembic>=1.8.0",
        "pytest>=7.0.0",
        "pytest-asyncio>=0.21.0",
        "pytest-cov>=4.0.0",
        "httpx>=0.24.0",
        "websockets>=11.0",

        # LLM providers
        "openai>=1.0.0",
        "anthropic>=0.18.0",
    ],

    # Console script entry points
    entry_points={
        "console_scripts": [
            "atom-os=cli.main:main_cli",
        ],
    },

    # Package metadata
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],

    # Keywords for PyPI
    keywords="automation ai agents governance multi-agent llm business workflow",

    # Zip safe
    zip_safe=False,

    # Include data files
    package_data={
        "atom_os": ["templates/*", "static/*"],
    },
)
```

Follow Python packaging best practices:
- setuptools for compatibility
- console_scripts for CLI entry point
- Automatic dependency discovery from requirements.txt
- Version requirement (Python 3.11+)
- PyPI classifiers for discoverability
  </action>
  <verify>
```bash
# Verify setup.py created
test -f backend/setup.py
grep -n "name=\"atom-os\"" backend/setup.py
grep -n "entry_points" backend/setup.py
grep -n "atom-os=cli.main:main_cli" backend/setup.py
```
  </verify>
  <done>
setup.py created with:
- Package name: atom-os
- Entry point: atom-os command
- Dependencies from requirements.txt
- CLI dependencies (click)
- Python 3.11+ requirement
- PyPI classifiers for discoverability
  </done>
</task>

<task type="auto">
  <name>Create pyproject.toml for modern packaging</name>
  <files>backend/pyproject.toml</files>
  <action>
Create backend/pyproject.toml (50-80 lines):

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "atom-os"
version = "0.1.0"
description = "AI-powered business automation platform"
readme = "README.md"
requires-python = ">=3.11"
license = {text = "MIT"}
authors = [
    {name = "Atom Platform", email = "contact@atom-platform.dev"},
]
keywords = ["automation", "ai", "agents", "governance", "llm", "workflow"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Environment :: Console",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Software Development :: Libraries :: Application Frameworks",
    "Topic :: Scientific/Engineering :: Artificial Intelligence",
]

[project.urls]
Homepage = "https://github.com/rush86999/atom"
Documentation = "https://github.com/rush86999/atom/tree/main/docs"
Repository = "https://github.com/rush86999/atom"
"Bug Tracker" = "https://github.com/rush86999/atom/issues"

[project.scripts]
atom-os = "cli.main:main_cli"

[tool.setuptools]
zip_safe = false
```

This provides modern Python packaging alongside setup.py for compatibility.
  </action>
  <verify>
```bash
# Verify pyproject.toml created
test -f backend/pyproject.toml
grep -n "\[project.scripts\]" backend/pyproject.toml
grep -n "atom-os = " backend/pyproject.toml
```
  </verify>
  <done>
pyproject.toml created with:
- Modern Python packaging metadata
- Project scripts entry point
- Build system configuration
- URLs for homepage, docs, repository, issues
- Zip safe disabled (correct for CLI apps)
  </done>
</task>

<task type="auto">
  <name>Create CLI package init file</name>
  <files>backend/cli/__init__.py</files>
  <action>
Create backend/cli/__init__.py:

```python
"""
Atom OS CLI package.

Provides command-line interface for Atom OS platform.
"""

__version__ = "0.1.0"
```

This makes the cli directory a Python package for imports.
  </action>
  <verify>
```bash
# Verify init file created
test -f backend/cli/__init__.py
grep -n "__version__" backend/cli/__init__.py
```
  </verify>
  <done>
CLI package init created with:
- Package version metadata
- Docstring explaining CLI purpose
  </done>
</task>

<task type="auto">
  <name>Create installation tests</name>
  <files>backend/tests/test_cli_installer.py</files>
< <action>
Create backend/tests/test_cli_installer.py (150-200 lines):

```python
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
        # Mock database and cache for status check
        with patch('cli.main.get_governance_cache') as mock_cache:
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
```

Coverage targets:
- Installation files exist (setup.py, pyproject.toml)
- CLI commands work (help, status, config)
- Host mount confirmation flow
- Dependencies available
- Integration with main_api_app
  </action>
  <verify>
```bash
# Run tests
cd backend && pytest tests/test_cli_installer.py -v
# Should show 10+ tests passing
```
  </verify>
  <done>
CLI installer tests created:
- 3 tests for installation files (setup.py, pyproject.toml, CLI module)
- 3 tests for CLI commands (help, status, config)
- 2 tests for host mount confirmation
- 2 tests for dependency availability
- Total: 10+ tests with comprehensive coverage
  </done>
</task>

</tasks>

<verification>
After completion, verify:
1. setup.py exists with atom-os package and console_scripts entry point
2. pyproject.toml exists with [project.scripts] entry
3. CLI main.py exists with Click framework and commands
4. atom-os --help works and shows help message
5. atom-os status shows Atom OS status
6. atom-os config shows environment variables
7. Host mount confirmation shows security warnings
8. Tests cover installation, CLI commands, host mount
9. README.md updated with installation instructions
</verification>

<success_criteria>
- `pip install atom-os` installs Atom OS package
- `atom-os` command is available after installation
- CLI provides helpful startup messages
- Host mount option requires interactive confirmation
- Installation works on Python 3.11+
- All dependencies included in package
- Security warnings displayed for host mount
- Test coverage >80% for installer
</success_criteria>

<output>
After completion, create `.planning/phases/13-openclaw-integration/13-openclaw-integration-03-SUMMARY.md` with:
- Files created/modified
- Installation instructions
- CLI commands available
- Host mount confirmation details
- Security warnings included
- Test coverage results
</output>
