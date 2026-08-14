# -*- coding: utf-8 -*-
"""Coverage wave 106 — cli/enable.py (Enterprise Edition upgrade CLI).
Fully mocked (package feature service, subprocess.run) — no pip installs, no
real .env touched (isolated filesystems).

Covers: enable group no-arg, enterprise already-enabled, confirm declined,
success via --yes/--skip-deps (env rewritten), confirm 'y' path, dependency
install success + CalledProcessError, missing .env fail, workspace-id +
database-url flags (incl. next-steps branch), _update_env_for_enterprise
(replace vs prepend for edition/database/multi-user/monitoring/workspace,
in-place DATABASE_URL/WORKSPACE_ID rewrite), features command (personal +
enterprise lists, enterprise-active short-circuit), register_enable_command.
"""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import click
from click.testing import CliRunner

from cli import enable as cli_enable


def _svc(is_enterprise=False):
    svc = MagicMock()
    svc.is_enterprise = is_enterprise
    svc.edition.value = "enterprise" if is_enterprise else "personal"
    return svc


def _feature_svc():
    svc = MagicMock()
    svc.is_enterprise = False
    svc.edition.value = "personal"
    svc.get_personal_features.return_value = {"multi_user", "sso"}
    svc.get_enterprise_features.return_value = {"audit_trail", "rate_limiting"}
    fi = SimpleNamespace(name="Feature X", description="Does things")
    svc.get_feature_info.return_value = fi
    svc.is_feature_enabled.side_effect = lambda f: f == "multi_user"
    return svc


def _write_env(content):
    Path(".env").write_text(content)
    return Path(".env")


def _invoke(*args, input=None):
    runner = CliRunner()
    return runner.invoke(cli_enable.enable, list(args), input=input)


def test_group_no_args_shows_help():
    res = _invoke()
    assert res.exit_code == 2
    assert "Usage:" in res.output


def test_enterprise_already_enabled():
    with patch("core.package_feature_service.get_package_feature_service", return_value=_svc(True)):
        res = _invoke("enterprise")
    assert res.exit_code == 0
    assert "already enabled!" in res.output
    assert "Current edition: enterprise" in res.output


def test_enterprise_confirm_declined():
    with patch("core.package_feature_service.get_package_feature_service", return_value=_svc(False)):
        res = _invoke("enterprise", input="n\n")
    assert res.exit_code == 0
    assert "Cancelled." in res.output


def test_enterprise_success_yes_skipdeps():
    runner = CliRunner()
    with runner.isolated_filesystem():
        env_file = _write_env("ATOM_EDITION=personal\nDATABASE_URL=sqlite:///x.db\n"
                              "ATOM_MULTI_USER_ENABLED=false\nATOM_MONITORING_ENABLED=false\n")
        with patch("core.package_feature_service.get_package_feature_service", return_value=_svc(False)), \
             patch("subprocess.run") as sub_run:
            res = runner.invoke(cli_enable.enable, ["enterprise", "--yes", "--skip-deps"])
        assert res.exit_code == 0
        assert "Enterprise Edition enabled!" in res.output
        sub_run.assert_not_called()
        content = env_file.read_text()
        assert "ATOM_EDITION=enterprise" in content
        assert "ATOM_MULTI_USER_ENABLED=true" in content
        assert "ATOM_MONITORING_ENABLED=true" in content
        assert "DATABASE_URL=sqlite:///x.db" in content


def test_enterprise_confirm_yes_proceeds():
    runner = CliRunner()
    with runner.isolated_filesystem():
        _write_env("ATOM_EDITION=personal\n")
        with patch("core.package_feature_service.get_package_feature_service", return_value=_svc(False)):
            res = runner.invoke(cli_enable.enable, ["enterprise", "--skip-deps"], input="y\n")
        assert res.exit_code == 0
        assert "ATOM_EDITION=enterprise" in Path(".env").read_text()


def test_enterprise_installs_dependencies():
    runner = CliRunner()
    with runner.isolated_filesystem():
        _write_env("ATOM_EDITION=personal\n")
        with patch("core.package_feature_service.get_package_feature_service", return_value=_svc(False)), \
             patch("subprocess.run") as sub_run:
            res = runner.invoke(cli_enable.enable, ["enterprise", "--yes"])
        assert res.exit_code == 0
        assert "Dependencies installed" in res.output
        sub_run.assert_called_once()
        assert sub_run.call_args.args[0][:2] == [click.__file__ and __import__("sys").executable,
                                                 "-m"]


def test_enterprise_deps_install_failure():
    runner = CliRunner()
    with runner.isolated_filesystem():
        _write_env("ATOM_EDITION=personal\n")
        with patch("core.package_feature_service.get_package_feature_service", return_value=_svc(False)), \
             patch("subprocess.run", side_effect=__import__("subprocess").CalledProcessError(1, "pip")):
            res = runner.invoke(cli_enable.enable, ["enterprise", "--yes"])
        assert res.exit_code == 1
        assert "Failed to install" in res.output
        assert "pip install atom-os[enterprise]" in res.output


def test_enterprise_missing_env_file():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with patch("core.package_feature_service.get_package_feature_service", return_value=_svc(False)):
            res = runner.invoke(cli_enable.enable, ["enterprise", "--yes", "--skip-deps"])
        assert res.exit_code == 1
        assert "run 'atom init' first" in res.output


def test_enterprise_workspace_id():
    runner = CliRunner()
    with runner.isolated_filesystem():
        _write_env("ATOM_EDITION=personal\n")
        with patch("core.package_feature_service.get_package_feature_service", return_value=_svc(False)):
            res = runner.invoke(cli_enable.enable, ["enterprise", "--yes", "--skip-deps", "--workspace-id", "acme"])
        assert res.exit_code == 0
        assert "WORKSPACE_ID=acme" in Path(".env").read_text()


def test_enterprise_database_url_flag():
    runner = CliRunner()
    with runner.isolated_filesystem():
        _write_env("ATOM_EDITION=personal\nDATABASE_URL=sqlite:///x.db\n")
        with patch("core.package_feature_service.get_package_feature_service", return_value=_svc(False)):
            res = runner.invoke(
                cli_enable.enable, ["enterprise", "--yes", "--skip-deps", "--database-url", "postgresql://u/p"]
            )
        assert res.exit_code == 0
        assert "DATABASE_URL=postgresql://u/p" in Path(".env").read_text()
        assert "createdb atom" not in res.output


def test_enterprise_no_db_url_shows_postgres_steps():
    runner = CliRunner()
    with runner.isolated_filesystem():
        _write_env("ATOM_EDITION=personal\n")
        with patch("core.package_feature_service.get_package_feature_service", return_value=_svc(False)):
            res = runner.invoke(cli_enable.enable, ["enterprise", "--yes", "--skip-deps"])
        assert res.exit_code == 0
        assert "createdb atom" in res.output


# ============================================================================
# _update_env_for_enterprise
# ============================================================================

def test_update_env_replaces_existing_values(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("ATOM_EDITION=personal\nDATABASE_URL=sqlite:///a.db\n"
                        "ATOM_MULTI_USER_ENABLED=false\nATOM_MONITORING_ENABLED=false\n"
                        "WORKSPACE_ID=old\n")
    cli_enable._update_env_for_enterprise(env_file, "postgresql://new/db", "new-ws")
    content = env_file.read_text()
    assert "ATOM_EDITION=enterprise" in content
    assert "DATABASE_URL=postgresql://new/db" in content
    assert "ATOM_MULTI_USER_ENABLED=true" in content
    assert "ATOM_MONITORING_ENABLED=true" in content
    assert "WORKSPACE_ID=new-ws" in content


def test_update_env_prepends_missing_keys(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("PORT=8000\n")
    cli_enable._update_env_for_enterprise(env_file, "postgresql://new/db", "ws9")
    content = env_file.read_text()
    assert "ATOM_EDITION=enterprise" in content
    assert "DATABASE_URL=postgresql://new/db" in content
    assert "ATOM_MULTI_USER_ENABLED=true" in content
    assert "ATOM_MONITORING_ENABLED=true" in content
    assert "WORKSPACE_ID=ws9" in content
    assert "PORT=8000" in content


def test_update_env_no_db_no_workspace(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("ATOM_EDITION=personal\n")
    cli_enable._update_env_for_enterprise(env_file, None, None)
    content = env_file.read_text()
    assert "ATOM_EDITION=enterprise" in content
    assert "DATABASE_URL=" not in content
    assert "WORKSPACE_ID=" not in content


def test_update_env_database_url_mid_file(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("A=1\nDATABASE_URL=sqlite:///a.db\nB=2\n")
    cli_enable._update_env_for_enterprise(env_file, "postgresql://mid/db", None)
    lines = env_file.read_text().split("\n")
    assert "DATABASE_URL=postgresql://mid/db" in lines
    assert "A=1" in lines and "B=2" in lines


# ============================================================================
# features
# ============================================================================

def test_features_lists_both_editions():
    with patch("core.package_feature_service.get_package_feature_service", return_value=_feature_svc()):
        res = _invoke("features")
    assert res.exit_code == 0
    assert "Atom Edition Features" in res.output
    assert "Feature X: Does things" in res.output
    assert "Personal Edition Features:" in res.output
    assert "Enterprise Edition Features:" in res.output
    assert "Enable Enterprise features:" in res.output


def test_features_enterprise_active_no_hint():
    svc = _feature_svc()
    svc.is_enterprise = True
    with patch("core.package_feature_service.get_package_feature_service", return_value=svc):
        res = _invoke("features")
    assert res.exit_code == 0
    assert "Enable Enterprise features:" not in res.output


def test_register_enable_command():
    group = click.Group()
    cli_enable.register_enable_command(group)
    assert "enable" in group.commands
