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
      provides: CLI entry point for atom-os command
      min_lines: 100
      exports: ["main", "start_atom"]
    - path: backend/pyproject.toml
      provides: Modern Python packaging configuration
      contains: "[project]", "[project.scripts]"
  key_links:
    - from: backend/setup.py
      to: backend/main_api_app.py
      via: Import and start of FastAPI app
      pattern: "from main_api_app import app"
    - from: backend/cli/main.py
      to: backend/main_api_app.py
      via: uvicorn.run() to start server
      pattern: "uvicorn.run\(app"
    - from: backend/setup.py
      to: backend/requirements.txt
      via: install_requires list
      pattern: "install_requires="
---

<objective>
Implement Simplified Python Installer (pip install atom-os)

Create a single-command installer using Python packaging standards (setuptools + console_scripts) that enables `pip install atom-os` followed by `atom-os` to start the platform, with optional host filesystem mount support.

Purpose: Simplify Atom installation and startup for personal edition users while maintaining compatibility with existing development workflow. Provide clear warnings about security implications of host mount feature.

Output: setup.py package configuration, CLI entry point (cli/main.py), pyproject.toml for modern packaging, updated README with installation instructions, and tests for CLI functionality.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/13-openclaw-integration/13-RESEARCH.md

# Python Packaging Standards
@backend/main_api_app.py            # FastAPI application entry point
@backend/requirements.txt           # Existing dependencies
@README.md                          # Documentation (root level)
@backend/Dockerfile                 # Container setup reference
</context>

<tasks>

<task type="auto">
  <name>Create setup.py package configuration</name>
  <files>backend/setup.py</files>
  <action>
    Create backend/setup.py with:

    1. Standard setuptools configuration:
       from setuptools import setup, find_packages

       setup(
           name="atom-os",
           version="1.0.0",
           description="Atom - AI-Powered Business Automation Platform (Personal Edition)",
           long_description=open("README.md").read() if exists else description,
           long_description_content_type="text/markdown",
           author="Atom Team",
           author_email="hello@atom-platform.com",
           url="https://github.com/atom-platform/atom",
           packages=find_packages(exclude=["tests*", "docs*"]),
           include_package_data=True,
           python_requires=">=3.11",

    2. Dependencies from requirements.txt:
       install_requires=[
           "fastapi>=0.104.0",
           "uvicorn[standard]>=0.24.0",
           "sqlalchemy>=2.0.0",
           "pydantic>=2.0.0",
           "python-multipart>=0.0.6",
           "python-jose[cryptography]>=3.3.0",
           "passlib[bcrypt]>=1.7.4",
           "alembic>=1.12.0",
           "click>=8.1.0",
           # Add other core dependencies from requirements.txt
           # Exclude: development tools (pytest, black, etc.)
       ],

    3. Console scripts entry point:
       entry_points={
           "console_scripts": [
               "atom-os=cli.main:main",
           ],
       },

    4. Classifiers:
       - Development Status :: 4 - Beta
       - Intended Audience :: Developers
       - License :: OSI Approved :: MIT License
       - Programming Language :: Python :: 3.11
       - Programming Language :: Python :: 3.12

    5. Optional: extras_require for development:
       extras_require={
           "dev": [
               "pytest>=7.4.0",
               "pytest-asyncio>=0.21.0",
               "black>=23.0.0",
               "ruff>=0.1.0",
           ],
       }

    DO NOT include test files or documentation in package
    DO include all core modules, API routes, tools
  </action>
  <verify>grep -n "name=\|entry_points=\|install_requires=" backend/setup.py returns configuration</verify>
  <done>setup.py defines atom-os package with console_scripts entry point</done>
</task>

<task type="auto">
  <name>Create CLI entry point with Click</name>
  <files>backend/cli/__init__.py backend/cli/main.py</files>
  <action>
    Create backend/cli/__init__.py (empty file with docstring)

    Create backend/cli/main.py with:

    1. Imports:
       import click
       import sys
       import os
       from pathlib import Path

    2. Version constant:
       __version__ = "1.0.0"

    3. @click.command()
    4. @click.option("--port", default=8000, help="Port to run on", show_default=True)
    5. @click.option("--host", default="0.0.0.0", help="Host to bind to", show_default=True)
    6. @click.option("--host-mount", is_flag=True, help="Enable host filesystem mount (AUTONOMOUS agents only)")
    7. @click.option("--reload", is_flag=True, help="Enable auto-reload for development")
    8. @click.option("--workers", default=1, help="Number of worker processes", show_default=True)
    9. @click.option("--log-level", default="info", help="Log level", show_default=True,
                    type=click.Choice(["debug", "info", "warning", "error"], case_sensitive=False))
    10. @click.version_option(version=__version__)

    11. def main(port, host, host_mount, reload, workers, log_level):
        """
        Atom OS - Personal Edition

        Start your local AI agent workforce with governance-first security.

        Example:
            atom-os --port 8000

        For host filesystem access (AUTONOMOUS agents only):
            atom-os --host-mount --port 8000
        """
        # Validate host mount option
        if host_mount:
            click.echo(click.style("WARNING: Host filesystem mount enabled!", fg="yellow", bold=True))
            click.echo("AUTONOMOUS agents will have access to:")
            click.echo(f"  - {os.getenv('HOME', '~')} (home directory)")
            click.echo(f"  - {os.getcwd()} (current directory)")
            click.echo()
            if not click.confirm("Continue with host mount enabled?", default=False):
                click.echo("Startup cancelled. Run without --host-mount for safer operation.")
                sys.exit(0)

        # Display startup banner
        click.echo(click.style("=" * 60, fg="blue"))
        click.echo(click.style(f"  Atom OS v{__version__} - Personal Edition", fg="blue", bold=True))
        click.echo(click.style("  AI-Powered Business Automation Platform", fg="blue"))
        click.echo(click.style("=" * 60, fg="blue"))
        click.echo()

        # Show configuration
        click.echo(f"Starting on http://{host}:{port}")
        if host_mount:
            click.echo(click.style("  Host mount: ENABLED", fg="yellow"))
        else:
            click.echo("  Host mount: DISABLED (safer)")
        click.echo(f"  Workers: {workers}")
        click.echo(f"  Log level: {log_level}")
        click.echo()

        # Import and run uvicorn
        try:
            import uvicorn
            from main_api_app import app

            # Configure environment for host mount
            if host_mount:
                os.environ["HOST_MOUNT_ENABLED"] = "true"
                os.environ["HOST_MOUNT_PREFIX"] = "/host"

            # Start server
            uvicorn.run(
                app,
                host=host,
                port=port,
                reload=reload,
                workers=1 if reload else workers,
                log_level=log_level
            )
        except ImportError as e:
            click.echo(click.style(f"Error: {e}", fg="red"))
            click.echo("Please ensure all dependencies are installed:")
            click.echo("  pip install atom-os")
            sys.exit(1)
        except Exception as e:
            click.echo(click.style(f"Failed to start: {e}", fg="red"))
            sys.exit(1)

    12. if __name__ == "__main__":
        main()

    Import click for CLI framework
    Use click.style() for colored output
    Use click.confirm() for host mount confirmation
  </action>
  <verify>grep -n "@click.command\|def main\|atom-os" backend/cli/main.py returns CLI definition</verify>
  <done>CLI entry point provides atom-os command with configurable options</done>
</task>

<task type="auto">
  <name>Create pyproject.toml for modern Python packaging</name>
  <files>backend/pyproject.toml</files>
  <action>
    Create backend/pyproject.toml with:

    1. Build system configuration:
       [build-system]
       requires = ["setuptools>=61.0", "wheel"]
       build-backend = "setuptools.build_meta"

    2. Project metadata (modern alternative to setup.py fields):
       [project]
       name = "atom-os"
       version = "1.0.0"
       description = "Atom - AI-Powered Business Automation Platform"
       readme = "README.md"
       requires-python = ">=3.11"
       license = {text = "MIT"}
       authors = [
           {name = "Atom Team", email = "hello@atom-platform.com"},
       ]
       keywords = ["ai", "automation", "agents", "business", "governance"]
       classifiers = [
           "Development Status :: 4 - Beta",
           "Intended Audience :: Developers",
           "License :: OSI Approved :: MIT License",
           "Programming Language :: Python :: 3.11",
           "Programming Language :: Python :: 3.12",
       ]

    3. Dependencies (reference setup.py for consistency):
       [project.optional-dependencies]
       dev = ["pytest>=7.4.0", "pytest-asyncio>=0.21.0", "black>=23.0.0"]

    4. Console scripts (modern alternative to entry_points):
       [project.scripts]
       atom-os = "cli.main:main"

    5. Tool configurations:
       [tool.black]
       line-length = 88
       target-version = ["py311"]

       [tool.ruff]
       line-length = 88
       select = ["E", "F"]

       [tool.pytest.ini_options]
       testpaths = ["tests"]
       python_files = ["test_*.py"]
       asyncio_mode = "auto"

    Note: Keep setup.py for backwards compatibility with older pip versions
    pyproject.toml is the modern standard but setup.py still works
  </action>
  <verify>grep -n "\\[build-system\\]\\|\\[project\\]\\|\\[project.scripts\\]" backend/pyproject.toml returns sections</verify>
  <done>pyproject.toml provides modern Python packaging configuration</done>
</task>

<task type="auto">
  <name>Update README with installation instructions</name>
  <files>README.md</files>
  <action>
    Update README.md (root level) with:

    1. Add Quick Start section at top:
       ## Quick Start (Personal Edition)

       ### Install via pip
       ```bash
       pip install atom-os
       ```

       ### Start Atom OS
       ```bash
       atom-os
       ```

       Atom will start on http://localhost:8000

       ### With Host Filesystem Access (Optional)
       For AUTONOMOUS agents to access your files:
       ```bash
       atom-os --host-mount
       ```

       WARNING: Host mount allows AUTONOMOUS agents to read/write your filesystem.
       Only enable in isolated environments with trusted agents.

    2. Add CLI Options section:
       ## CLI Options

       ```bash
       atom-os [OPTIONS]

       Options:
         --port TEXT          Port to run on [default: 8000]
         --host TEXT          Host to bind to [default: 0.0.0.0]
         --host-mount         Enable host filesystem mount
         --reload             Enable auto-reload (development)
         --workers INTEGER    Number of workers [default: 1]
         --log-level TEXT     Log level: debug, info, warning, error [default: info]
         --help               Show help message
         --version            Show version
       ```

    3. Update Development section (preserve existing):
       Keep existing development setup instructions for contributors
       Add note about editable install for development:
       ```bash
       # For development (editable install)
       cd backend
       pip install -e .
       ```

    DO NOT remove existing content
    DO reorganize sections: Quick Start first, then Development, then full documentation
    PRESERVE all existing README content
  </action>
  <verify>grep -n "Quick Start\|pip install atom-os\|CLI Options" README.md returns new sections</verify>
  <done>README includes Quick Start with pip install and CLI options documentation</done>
</task>

<task type="auto">
  <name>Write tests for CLI installer</name>
  <files>backend/tests/test_cli_installer.py</files>
  <action>
    Create backend/tests/test_cli_installer.py with:

    1. Test imports:
       import pytest
       from click.testing import CliRunner
       from unittest.mock import patch, Mock
       from cli.main import main, __version__

    2. Test runner fixture:
       @pytest.fixture
       def runner():
           return CliRunner()

    3. Test version option:
       def test_version_option(runner):
           result = runner.invoke(main, ["--version"])
           assert result.exit_code == 0
           assert __version__ in result.output

    4. Test help option:
       def test_help_option(runner):
           result = runner.invoke(main, ["--help"])
           assert result.exit_code == 0
           assert "Atom OS" in result.output
           assert "--port" in result.output
           assert "--host-mount" in result.output

    5. Test host mount confirmation:
       @patch("cli.main.click.confirm")
       def test_host_mount_requires_confirmation(mock_confirm, runner):
           mock_confirm.return_value = False
           result = runner.invoke(main, ["--host-mount"])
           assert "cancelled" in result.output.lower()

       @patch("cli.main.click.confirm")
       @patch("cli.main.uvicorn.run")
       def test_host_mount_confirmed_starts_server(mock_run, mock_confirm, runner):
           mock_confirm.return_value = True
           result = runner.invoke(main, ["--host-mount"])
           assert result.exit_code == 0
           mock_run.assert_called_once()

    6. Test startup banner:
       @patch("cli.main.uvicorn.run")
       def test_startup_banner_displayed(mock_run, runner):
           result = runner.invoke(main, [])
           assert "Atom OS" in result.output
           assert "=" in result.output

    7. Test port configuration:
       @patch("cli.main.uvicorn.run")
       def test_custom_port_passed_to_uvicorn(mock_run, runner):
           runner.invoke(main, ["--port", "9000"])
           call_kwargs = mock_run.call_args[1]
           assert call_kwargs["port"] == 9000

    8. Test log level configuration:
       @patch("cli.main.uvicorn.run")
       def test_log_level_passed_to_uvicorn(mock_run, runner):
           runner.invoke(main, ["--log-level", "debug"])
           call_kwargs = mock_run.call_args[1]
           assert call_kwargs["log_level"] == "debug"

    9. Test environment variables set for host mount:
       @patch("cli.main.uvicorn.run")
       @patch.dict("os.environ", {}, clear=True)
       def test_host_mount_sets_environment(mock_run, runner):
           runner.invoke(main, ["--host-mount"])
           import os
           assert os.environ.get("HOST_MOUNT_ENABLED") == "true"

    10. Test import error handling:
        @patch("cli.main.uvicorn", side_effect=ImportError("No module named 'uvicorn'"))
        def test_import_error_shows_helpful_message(mock_uvicorn, runner):
            result = runner.invoke(main, [])
            assert "Error" in result.output
            assert "pip install" in result.output

    Use CliRunner from Click testing utilities
    Mock uvicorn.run to prevent actual server startup
    Mock click.confirm to test host mount flow
  </action>
  <verify>pytest backend/tests/test_cli_installer.py -v returns passing tests</verify>
  <done>CLI tests validate version, help, host mount confirmation, startup banner, and configuration</done>
</task>

</tasks>

<verification>
1. Package Configuration:
   - setup.py defines atom-os package with proper metadata
   - console_scripts entry point creates atom-os command
   - Dependencies include FastAPI, Uvicorn, SQLAlchemy, etc.
   - Python version requires 3.11+

2. CLI Entry Point:
   - Click framework provides command parsing
   - atom-os command starts FastAPI application
   - Options: port, host, host-mount, reload, workers, log-level
   - Host mount requires confirmation with warning
   - Startup banner displays configuration

3. Modern Packaging:
   - pyproject.toml provides [build-system], [project], [project.scripts]
   - Tool configurations for Black, Ruff, Pytest
   - Compatible with both setup.py and pyproject.toml

4. Documentation:
   - README updated with Quick Start section
   - pip install atom-os instructions
   - CLI options documented
   - Host mount security warning

5. Error Handling:
   - Import errors show helpful message
   - Host mount cancellation exits gracefully
   - Invalid options rejected by Click

6. Test Coverage:
   - Version option test
   - Help option test
   - Host mount confirmation flow
   - Startup banner display
   - Port/log-level configuration
   - Environment variable setting
   - Import error handling
</verification>

<success_criteria>
1. User can run `pip install atom-os` to install Atom
2. User can run `atom-os` to start the platform
3. CLI options configure port, host, workers, log level
4. --host-mount flag requires confirmation with security warning
5. pyproject.toml provides modern Python packaging
6. README includes Quick Start and CLI documentation
7. Tests validate CLI functionality
8. Installation works on Python 3.11+
</success_criteria>

<output>
After completion, create `.planning/phases/13-openclaw-integration/13-openclaw-integration-03-SUMMARY.md` with:
- Implemented setup.py package configuration with console_scripts
- Created CLI entry point (cli/main.py) with Click framework
- Added pyproject.toml for modern Python packaging
- Updated README with installation instructions
- Comprehensive CLI tests for validation

Include code snippets for:
- setup.py entry_points configuration
- Click command with options
- Host mount confirmation flow
- pyproject.toml [project.scripts] configuration
</output>
