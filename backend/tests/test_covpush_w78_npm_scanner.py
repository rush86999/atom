# -*- coding: utf-8 -*-
"""Coverage wave 78 — core/npm_dependency_scanner. All subprocess/network
activity mocked; real temp dir used for package.json staging.

Bug-driven TDD (wave 78):
- RED: _run_snyk_check dropped ALL Snyk findings when a vulnerability's
  identifiers["CVE"] list was empty — `[0]` raised IndexError, the whole
  function fell into the generic except and returned {"vulnerabilities": []}
  (false-negative). Fixed with `or ["UNKNOWN"]`.
- RED: _run_package_manager_audit never extracted cwe/title from the npm audit
  `via[]` array (real npm audit JSON puts CWE + title in via[0], not at the
  top level) — cve_id was always "UNKNOWN" and advisory always "No description".
  Fixed to fall back to via[0] when present.

Coverage:
- scan_packages: empty input, full happy path (install+list+audit+snyk), no
  vulns, install timeout warning, generic install failure, unknown manager.
- _create_package_json: scoped ±version, plain ±version.
- _install_packages: npm/yarn/pnpm commands, unknown manager, non-zero exit,
  timeout re-raise.
- _build_dependency_tree: parse ok, JSONDecodeError, non-zero exit, timeout,
  generic exception.
- _run_package_manager_audit: npm/yarn/pnpm, vuln dict vs list shapes, range
  str vs list, via[0] fallback, JSONDecodeError, non-zero exit, timeout,
  generic exception.
- _run_snyk_check: CLI missing, clean (rc 0), findings parsed, CVE identifiers
  absent/empty, JSONDecodeError, timeout, generic exception.
"""
import json
import shutil
import subprocess
from unittest.mock import MagicMock, patch

import pytest

import core.npm_dependency_scanner as ns
from core.npm_dependency_scanner import NpmDependencyScanner


def _completed(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(args=[], returncode=returncode,
                                       stdout=stdout, stderr=stderr)


def _audit_json(vulns=None):
    return json.dumps({"vulnerabilities": vulns or {}})


@pytest.fixture(autouse=True)
def _no_snyk_key(monkeypatch):
    monkeypatch.delenv("SNYK_API_KEY", raising=False)


class TestScanPackages:
    def test_empty_packages(self):
        result = NpmDependencyScanner().scan_packages([])
        assert result["safe"] is True
        assert result["vulnerabilities"] == []
        assert result["dependency_tree"] == {}
        assert result["warning"] is None

    def test_full_scan_with_vulnerabilities(self):
        audit_out = _audit_json({
            "lodash": {
                "severity": "high",
                "via": [{"cwe": ["CWE-787"], "title": "Out-of-bounds Write in lodash"}],
                "range": ">=4.17.12 <4.17.21",
            }
        })
        tree_out = json.dumps({
            "dependencies": {
                "lodash": {"version": "4.17.15", "resolved": "https://r/lodash.tgz"}
            }
        })
        scanner = NpmDependencyScanner("snyk-key")
        with patch.object(ns.shutil, "which", return_value="/usr/bin/snyk"):
            with patch.object(ns.subprocess, "run", side_effect=[
                _completed(0),                       # npm install
                _completed(0, stdout=tree_out),      # npm list
                _completed(1, stdout=audit_out),     # npm audit (rc 1 = vulns)
                _completed(1, stdout=json.dumps({    # snyk test
                    "vulnerabilities": [{
                        "identifiers": {"CVE": ["CVE-2020-8203"]},
                        "severity": "medium",
                        "packageName": "lodash",
                        "semver": {"vulnerable": ["<4.17.21"]},
                        "title": "Prototype Pollution",
                    }]
                })),
            ]):
                result = scanner.scan_packages(["lodash@4.17.15"])
        assert result["safe"] is False
        assert result["warning"] is None
        assert len(result["vulnerabilities"]) == 2
        npm_vuln = result["vulnerabilities"][0]
        assert npm_vuln["source"] == "npm-audit"
        assert npm_vuln["package"] == "lodash"
        assert npm_vuln["severity"] == "high"
        assert npm_vuln["affected_versions"] == [">=4.17.12 <4.17.21"]
        snyk_vuln = result["vulnerabilities"][1]
        assert snyk_vuln["source"] == "snyk"
        assert snyk_vuln["cve_id"] == "CVE-2020-8203"
        assert snyk_vuln["advisory"] == "Prototype Pollution"
        assert result["dependency_tree"]["lodash"]["version"] == "4.17.15"

    def test_full_scan_clean(self):
        scanner = NpmDependencyScanner()
        with patch.object(ns.shutil, "which", return_value="/usr/bin/snyk"):
            with patch.object(ns.subprocess, "run", side_effect=[
                _completed(0),
                _completed(0, stdout=json.dumps({"dependencies": {}})),
                _completed(0, stdout=_audit_json()),
                _completed(0, stdout=""),
            ]):
                result = scanner.scan_packages(["express"])
        assert result["safe"] is True
        assert result["vulnerabilities"] == []

    def test_install_timeout_returns_warning(self):
        scanner = NpmDependencyScanner()
        with patch.object(ns.subprocess, "run",
                          side_effect=subprocess.TimeoutExpired(["npm"], 120)):
            result = scanner.scan_packages(["express"])
        assert result["safe"] is True
        assert result["warning"] == "Scan timed out after 120s - unable to verify safety"

    def test_install_failure_returns_warning(self):
        scanner = NpmDependencyScanner()
        with patch.object(ns.subprocess, "run",
                          side_effect=subprocess.CalledProcessError(1, ["npm"])):
            result = scanner.scan_packages(["express"])
        assert result["safe"] is True
        assert "Scan failed" in result["warning"]

    def test_unknown_package_manager_fails_gracefully(self):
        scanner = NpmDependencyScanner()
        with patch.object(ns.subprocess, "run") as run_mock:
            result = scanner.scan_packages(["express"], package_manager="bogus")
        run_mock.assert_not_called()
        assert result["safe"] is True
        assert "Scan failed" in result["warning"]


class TestCreatePackageJson:
    def test_scoped_with_version(self):
        deps = NpmDependencyScanner()._create_package_json(
            ["@angular/core@12.0.0", "lodash@4.17.21", "express", "react@^18.0.0"]
        )["dependencies"]
        assert deps["@angular/core"] == "12.0.0"
        assert deps["lodash"] == "4.17.21"
        assert deps["express"] == "*"
        assert deps["react"] == "^18.0.0"

    def test_scoped_without_version(self):
        deps = NpmDependencyScanner()._create_package_json(["@scope/name"])["dependencies"]
        assert deps["@scope/name"] == "*"


class TestInstallPackages:
    def test_npm_command(self):
        scanner = NpmDependencyScanner()
        with patch.object(ns.subprocess, "run", return_value=_completed(0)) as run_mock:
            scanner._install_packages("/tmp/wd", "npm")
        cmd = run_mock.call_args.args[0]
        assert cmd[:3] == ["npm", "install", "--ignore-scripts"]
        assert run_mock.call_args.kwargs["timeout"] == 120

    def test_yarn_command(self):
        with patch.object(ns.subprocess, "run", return_value=_completed(0)) as run_mock:
            NpmDependencyScanner()._install_packages("/tmp/wd", "yarn")
        assert run_mock.call_args.args[0][0] == "yarn"

    def test_pnpm_command(self):
        with patch.object(ns.subprocess, "run", return_value=_completed(0)) as run_mock:
            NpmDependencyScanner()._install_packages("/tmp/wd", "pnpm")
        assert run_mock.call_args.args[0][0] == "pnpm"

    def test_unknown_manager_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown package manager"):
            NpmDependencyScanner()._install_packages("/tmp/wd", "bogus")

    def test_nonzero_exit_raises(self):
        with patch.object(ns.subprocess, "run",
                          return_value=_completed(1, stderr="boom")):
            with pytest.raises(subprocess.CalledProcessError):
                NpmDependencyScanner()._install_packages("/tmp/wd", "npm")

    def test_timeout_reraises(self):
        with patch.object(ns.subprocess, "run",
                          side_effect=subprocess.TimeoutExpired(["npm"], 120)):
            with pytest.raises(subprocess.TimeoutExpired):
                NpmDependencyScanner()._install_packages("/tmp/wd", "npm")


class TestBuildDependencyTree:
    def test_parses_dependencies(self):
        stdout = json.dumps({
            "dependencies": {
                "lodash": {"version": "4.17.21", "resolved": "https://r/lodash"},
                "bare": {},
            }
        })
        with patch.object(ns.subprocess, "run", return_value=_completed(0, stdout=stdout)):
            tree = NpmDependencyScanner()._build_dependency_tree("/tmp/wd")
        assert tree["lodash"] == {"version": "4.17.21", "resolved": "https://r/lodash"}
        assert tree["bare"]["version"] == "unknown"

    def test_json_decode_error_returns_empty(self):
        with patch.object(ns.subprocess, "run", return_value=_completed(0, stdout="not json")):
            assert NpmDependencyScanner()._build_dependency_tree("/tmp/wd") == {}

    def test_nonzero_exit_returns_empty(self):
        with patch.object(ns.subprocess, "run", return_value=_completed(1, stderr="nope")):
            assert NpmDependencyScanner()._build_dependency_tree("/tmp/wd") == {}

    def test_timeout_returns_empty(self):
        with patch.object(ns.subprocess, "run",
                          side_effect=subprocess.TimeoutExpired(["npm"], 30)):
            assert NpmDependencyScanner()._build_dependency_tree("/tmp/wd") == {}

    def test_generic_exception_returns_empty(self):
        with patch.object(ns.subprocess, "run", side_effect=OSError("exec")):
            assert NpmDependencyScanner()._build_dependency_tree("/tmp/wd") == {}


class TestRunPackageManagerAudit:
    def test_npm_audit_with_via_fallback(self):
        """RED (wave 78): real npm audit JSON stores cwe/title in via[0], not
        top-level — previously cve_id was always UNKNOWN and advisory always
        'No description'."""
        stdout = _audit_json({
            "axios": {
                "severity": "medium",
                "via": [{"cwe": ["CWE-79"], "title": "Cross-site Scripting in axios"}],
                "range": "<0.21.0",
            }
        })
        with patch.object(ns.subprocess, "run", return_value=_completed(1, stdout=stdout)):
            result = NpmDependencyScanner()._run_package_manager_audit("/tmp/wd", "npm")
        vuln = result["vulnerabilities"][0]
        assert vuln["cve_id"] == "CWE-79"
        assert vuln["advisory"] == "Cross-site Scripting in axios"
        assert vuln["affected_versions"] == ["<0.21.0"]
        assert vuln["source"] == "npm-audit"

    def test_vuln_info_as_list_and_range_as_str(self):
        stdout = _audit_json({
            "pkg-a": [
                {"severity": "high", "range": "<1.0.0", "title": "T1"},
                {"severity": "low", "range": ">=1.0.0", "title": "T2"},
            ]
        })
        with patch.object(ns.subprocess, "run", return_value=_completed(1, stdout=stdout)):
            result = NpmDependencyScanner()._run_package_manager_audit("/tmp/wd", "npm")
        assert len(result["vulnerabilities"]) == 2
        assert result["vulnerabilities"][0]["affected_versions"] == ["<1.0.0"]
        assert result["vulnerabilities"][1]["affected_versions"] == [">=1.0.0"]

    def test_clean_audit(self):
        with patch.object(ns.subprocess, "run",
                          return_value=_completed(0, stdout=_audit_json())):
            result = NpmDependencyScanner()._run_package_manager_audit("/tmp/wd", "npm")
        assert result["vulnerabilities"] == []

    def test_yarn_audit_command(self):
        with patch.object(ns.subprocess, "run",
                          return_value=_completed(0, stdout=_audit_json())) as run_mock:
            NpmDependencyScanner()._run_package_manager_audit("/tmp/wd", "yarn")
        assert run_mock.call_args.args[0] == ["yarn", "audit", "--json"]

    def test_pnpm_audit_command(self):
        with patch.object(ns.subprocess, "run",
                          return_value=_completed(0, stdout=_audit_json())) as run_mock:
            NpmDependencyScanner()._run_package_manager_audit("/tmp/wd", "pnpm")
        assert run_mock.call_args.args[0] == ["pnpm", "audit", "--json"]

    def test_unknown_manager_returns_empty(self):
        result = NpmDependencyScanner()._run_package_manager_audit("/tmp/wd", "bogus")
        assert result["vulnerabilities"] == []

    def test_nonzero_rc_returns_empty(self):
        with patch.object(ns.subprocess, "run", return_value=_completed(2, stderr="err")):
            assert NpmDependencyScanner()._run_package_manager_audit("/tmp/wd", "npm") == {
                "vulnerabilities": []
            }

    def test_json_decode_error_returns_empty(self):
        with patch.object(ns.subprocess, "run",
                          return_value=_completed(1, stdout="<html>error</html>")):
            assert NpmDependencyScanner()._run_package_manager_audit("/tmp/wd", "npm") == {
                "vulnerabilities": []
            }

    def test_timeout_returns_empty(self):
        with patch.object(ns.subprocess, "run",
                          side_effect=subprocess.TimeoutExpired(["npm"], 120)):
            assert NpmDependencyScanner()._run_package_manager_audit("/tmp/wd", "npm") == {
                "vulnerabilities": []
            }

    def test_generic_exception_returns_empty(self):
        with patch.object(ns.subprocess, "run", side_effect=OSError("boom")):
            assert NpmDependencyScanner()._run_package_manager_audit("/tmp/wd", "npm") == {
                "vulnerabilities": []
            }


class TestRunSnykCheck:
    def test_cli_missing_skips(self):
        with patch.object(ns.shutil, "which", return_value=None):
            result = NpmDependencyScanner("key")._run_snyk_check("/tmp/wd")
        assert result == {"vulnerabilities": []}

    def test_clean_run(self):
        with patch.object(ns.shutil, "which", return_value="/usr/bin/snyk"):
            with patch.object(ns.subprocess, "run", return_value=_completed(0, stdout="")):
                assert NpmDependencyScanner("key")._run_snyk_check("/tmp/wd") == {
                    "vulnerabilities": []
                }

    def test_findings_parsed(self):
        stdout = json.dumps({
            "vulnerabilities": [{
                "identifiers": {"CVE": ["CVE-1"]},
                "severity": "high",
                "packageName": "minimist",
                "semver": {"vulnerable": ["<0.2.1"]},
                "title": "Prototype Pollution",
            }]
        })
        with patch.object(ns.shutil, "which", return_value="/usr/bin/snyk"):
            with patch.object(ns.subprocess, "run", return_value=_completed(1, stdout=stdout)):
                result = NpmDependencyScanner("key")._run_snyk_check("/tmp/wd")
        vuln = result["vulnerabilities"][0]
        assert vuln["cve_id"] == "CVE-1"
        assert vuln["package"] == "minimist"
        assert vuln["source"] == "snyk"

    def test_empty_cve_list_does_not_drop_findings(self):
        """RED (wave 78): identifiers["CVE"] == [] made `[0]` raise IndexError,
        which silently dropped every Snyk finding for that package."""
        stdout = json.dumps({
            "vulnerabilities": [{
                "identifiers": {"CVE": [], "GHSA": ["GHSA-1"]},
                "severity": "high",
                "packageName": "minimist",
                "semver": {"vulnerable": ["<0.2.1"]},
                "title": "Prototype Pollution",
            }]
        })
        with patch.object(ns.shutil, "which", return_value="/usr/bin/snyk"):
            with patch.object(ns.subprocess, "run", return_value=_completed(1, stdout=stdout)):
                result = NpmDependencyScanner("key")._run_snyk_check("/tmp/wd")
        assert len(result["vulnerabilities"]) == 1
        assert result["vulnerabilities"][0]["cve_id"] == "UNKNOWN"
        assert result["vulnerabilities"][0]["advisory"] == "Prototype Pollution"

    def test_missing_cve_identifier_key(self):
        stdout = json.dumps({
            "vulnerabilities": [{
                "identifiers": {},
                "severity": "low",
                "packageName": "x",
                "semver": {},
                "title": "T",
            }]
        })
        with patch.object(ns.shutil, "which", return_value="/usr/bin/snyk"):
            with patch.object(ns.subprocess, "run", return_value=_completed(1, stdout=stdout)):
                result = NpmDependencyScanner("key")._run_snyk_check("/tmp/wd")
        assert result["vulnerabilities"][0]["cve_id"] == "UNKNOWN"

    def test_json_decode_error_returns_empty(self):
        with patch.object(ns.shutil, "which", return_value="/usr/bin/snyk"):
            with patch.object(ns.subprocess, "run",
                              return_value=_completed(1, stdout="not json")):
                assert NpmDependencyScanner("key")._run_snyk_check("/tmp/wd") == {
                    "vulnerabilities": []
                }

    def test_timeout_returns_empty(self):
        with patch.object(ns.shutil, "which", return_value="/usr/bin/snyk"):
            with patch.object(ns.subprocess, "run",
                              side_effect=subprocess.TimeoutExpired(["snyk"], 120)):
                assert NpmDependencyScanner("key")._run_snyk_check("/tmp/wd") == {
                    "vulnerabilities": []
                }

    def test_generic_exception_returns_empty(self):
        with patch.object(ns.shutil, "which", return_value="/usr/bin/snyk"):
            with patch.object(ns.subprocess, "run", side_effect=OSError("boom")):
                assert NpmDependencyScanner("key")._run_snyk_check("/tmp/wd") == {
                    "vulnerabilities": []
                }

    def test_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("SNYK_API_KEY", "env-key")
        assert NpmDependencyScanner().snyk_api_key == "env-key"
