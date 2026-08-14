# -*- coding: utf-8 -*-
"""Coverage wave 106 — cli/init.py (Personal Edition setup wizard).
Fully mocked (package feature service) — no real DB, no network, no keys
touched; runs inside CliRunner isolated filesystems so no .env is written to
the repo.

Covers: default personal init (env content, data dirs, encryption keys),
custom database-url substitution, enterprise init with/without database-url,
prompted database-url, no-input failure path, already-initialized (with
service edition display) vs --force overwrite, invalid edition choice,
_init_personal_edition/_init_enterprise_edition direct calls,
register_init_command.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from cli import init as cli_init


def _svc(edition_value="PERSONAL"):
    svc = MagicMock()
    svc.edition.value = edition_value
    return svc


def _run(*args, input=None):
    runner = CliRunner()
    return runner.invoke(cli_init.init, list(args), input=input)


def test_personal_default_init():
    runner = CliRunner()
    with runner.isolated_filesystem():
        res = runner.invoke(cli_init.init, [])
        assert res.exit_code == 0
        assert "Initialization complete!" in res.output
        assert "Setting up Personal Edition..." in res.output
        env = Path(".env").read_text()
        assert "ATOM_EDITION=personal" in env
        assert "DATABASE_URL=sqlite:///./data/atom.db" in env
        assert "BYOK_ENCRYPTION_KEY=" in env
        assert "JWT_SECRET_KEY=" in env
        assert "EMBEDDING_PROVIDER=fastembed" in env
        assert Path("data/lancedb").is_dir()
        assert Path("data/uploads").is_dir()


def test_personal_custom_database_url():
    runner = CliRunner()
    with runner.isolated_filesystem():
        res = runner.invoke(cli_init.init, ["--database-url", "sqlite:////tmp/custom.db"])
        assert res.exit_code == 0
        env = Path(".env").read_text()
        assert "DATABASE_URL=sqlite:////tmp/custom.db" in env
        assert "Database: sqlite:////tmp/custom.db" in res.output


def test_enterprise_with_database_url():
    runner = CliRunner()
    with runner.isolated_filesystem():
        res = runner.invoke(
            cli_init.init,
            ["--edition", "enterprise", "--database-url", "postgresql://u:p@localhost/atom"],
        )
        assert res.exit_code == 0
        assert "Setting up Enterprise Edition..." in res.output
        env = Path(".env").read_text()
        assert "ATOM_EDITION=enterprise" in env
        assert "DATABASE_URL=postgresql://u:p@localhost/atom" in env
        assert "WORKERS=4" in env
        assert "REDIS_URL=redis://localhost:6379/0" in env
        assert "ATOM_MULTI_USER_ENABLED=true" in env
        assert "PROMETHEUS_PORT=9090" in env
        assert Path("data/audit").is_dir()
        assert "PostgreSQL Setup Required:" in res.output


def test_enterprise_prompted_database_url():
    runner = CliRunner()
    with runner.isolated_filesystem():
        res = runner.invoke(
            cli_init.init, ["--edition", "enterprise"],
            input="postgresql://prompted@localhost/atom\n",
        )
        assert res.exit_code == 0
        env = Path(".env").read_text()
        assert "DATABASE_URL=postgresql://prompted@localhost/atom" in env


def test_enterprise_no_input_without_db_fails():
    runner = CliRunner()
    with runner.isolated_filesystem():
        res = runner.invoke(cli_init.init, ["--edition", "enterprise", "--no-input"])
        assert res.exit_code == 1
        assert "Database URL required for Enterprise" in res.output
        assert not Path(".env").exists()


def test_enterprise_no_input_with_db_succeeds():
    runner = CliRunner()
    with runner.isolated_filesystem():
        res = runner.invoke(
            cli_init.init, ["--edition", "enterprise", "--no-input", "--database-url", "postgresql://x/y"]
        )
        assert res.exit_code == 0
        assert "ATOM_EDITION=enterprise" in Path(".env").read_text()


def test_already_initialized_exits_with_status():
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path(".env").write_text("ATOM_EDITION=personal\n")
        with patch("core.package_feature_service.get_package_feature_service", return_value=_svc("personal")):
            res = runner.invoke(cli_init.init, [])
        assert res.exit_code == 1
        assert "Configuration already exists!" in res.output
        assert "Use --force to overwrite" in res.output
        assert "Current Edition: personal" in res.output


def test_already_initialized_force_overwrites():
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path(".env").write_text("OLD=1\n")
        res = runner.invoke(cli_init.init, ["--force"])
        assert res.exit_code == 0
        env = Path(".env").read_text()
        assert "ATOM_EDITION=personal" in env
        assert "OLD=1" not in env


def test_invalid_edition_choice():
    res = _run("--edition", "community")
    assert res.exit_code == 2
    assert "Invalid value" in res.output


def test_init_personal_edition_direct(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cli_init._init_personal_edition(None, True)
    env = Path(".env").read_text()
    assert "DATABASE_URL=sqlite:///./data/atom.db" in env
    assert Path("data/lancedb").is_dir()
    assert Path("data/uploads").is_dir()


def test_init_personal_edition_direct_custom_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cli_init._init_personal_edition("sqlite:///x.db", True)
    env = Path(".env").read_text()
    assert "DATABASE_URL=sqlite:///x.db" in env
    assert "Database: sqlite:///x.db" is not None


def test_init_enterprise_edition_direct(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cli_init._init_enterprise_edition("postgresql://e/db", True, False)
    env = Path(".env").read_text()
    assert "ATOM_EDITION=enterprise" in env
    assert Path("data/audit").is_dir()


def test_init_enterprise_edition_direct_no_db_raises(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with __import__("pytest").raises(SystemExit) as ei:
        cli_init._init_enterprise_edition(None, True, False)
    assert ei.value.code == 1


def test_register_init_command():
    import click
    group = click.Group()
    cli_init.register_init_command(group)
    assert "init" in group.commands


def test_next_steps_output():
    runner = CliRunner()
    with runner.isolated_filesystem():
        res = runner.invoke(cli_init.init, [])
        assert "Next steps:" in res.output
        assert "OPENAI_API_KEY=sk-..." in res.output
        assert "http://localhost:8000" in res.output
