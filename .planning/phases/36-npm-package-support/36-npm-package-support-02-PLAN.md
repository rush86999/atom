---
phase: 36-npm-package-support
plan: 02
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/core/npm_dependency_scanner.py
  - backend/core/npm_script_analyzer.py
  - backend/tests/test_npm_dependency_scanner.py
  - backend/tests/test_npm_script_analyzer.py
autonomous: true

must_haves:
  truths:
    - "NpmDependencyScanner runs npm audit --json and parses vulnerability output"
    - "NpmDependencyScanner runs Snyk check when SNYK_API_KEY is provided"
    - "NpmScriptAnalyzer detects malicious postinstall/preinstall script patterns"
    - "Scanner creates temporary package.json for scanning isolated packages"
    - "Timeout handling returns safe=True with warning (scanning failure != security issue)"
  artifacts:
    - path: backend/core/npm_dependency_scanner.py
      contains: class NpmDependencyScanner, scan_packages, _run_package_manager_audit, _run_snyk_check
    - path: backend/core/npm_script_analyzer.py
      contains: class NpmScriptAnalyzer, analyze_package_scripts, MALICIOUS_PATTERNS
    - path: backend/tests/test_npm_dependency_scanner.py
      contains: test_scan_packages, test_npm_audit, test_snyk_check
    - path: backend/tests/test_npm_script_analyzer.py
      contains: test_analyze_scripts, test_malicious_patterns
  key_links:
    - from: backend/core/npm_dependency_scanner.py
      to: npm audit CLI
      via: subprocess.run(["npm", "audit", "--json"])
      pattern: subprocess\.run.*npm.*audit
    - from: backend/core/npm_script_analyzer.py
      to: npm registry API
      via: requests.get(f"https://registry.npmjs.org/{package_name}")
      pattern: registry\.npmjs\.org
---

<objective>
Implement npm-specific dependency vulnerability scanner and postinstall script analyzer to detect security threats in npm packages before installation.

**Purpose:** Scan npm packages for known vulnerabilities (npm audit + Snyk) and malicious postinstall/preinstall scripts (credential theft, command execution, data exfiltration).

**Output:** NpmDependencyScanner for vulnerability scanning, NpmScriptAnalyzer for script threat detection, with comprehensive test coverage.

</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/phases/36-npm-package-support/36-RESEARCH.md
@backend/core/package_dependency_scanner.py (reference for Python scanner patterns)
@backend/core/models.py (PackageRegistry for understanding npm package types)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create NpmDependencyScanner with npm audit integration</name>
  <files>backend/core/npm_dependency_scanner.py</files>
  <action>
    Create NpmDependencyScanner class following the pattern from RESEARCH.md Pattern 2:

    1. Create file with imports:
       - subprocess, tempfile, json, os, logging
       - typing: Any, Dict, List, Optional
       - requests for npm registry API

    2. Implement class structure:
       ```python
       class NpmDependencyScanner:
           \"\"\"Scans npm packages for security vulnerabilities using npm audit + Snyk.\"\"\"

           def __init__(self, snyk_api_key: Optional[str] = None):
               self.snyk_api_key = snyk_api_key or os.getenv("SNYK_API_KEY")

           def scan_packages(self, packages: List[str], package_manager: str = "npm", cache_dir: Optional[str] = None) -> Dict[str, Any]:
               # Main scanning method
       ```

    3. Implement _create_package_json method:
       - Parse package specifiers (e.g., "lodash@4.17.21")
       - Return dict with name, version, private: true, dependencies

    4. Implement _run_package_manager_audit method:
       - Support npm, yarn, pnpm with --json flag
       - Parse JSON output for vulnerabilities
       - Return {"vulnerabilities": [...]}

    5. Implement timeout handling (120s default):
       - Return {"safe": True, "warning": "Scan timed out"} on timeout

    Use npm audit JSON format from RESEARCH.md lines 308-346.
  </action>
  <verify>
    python -c "from backend.core.npm_dependency_scanner import NpmDependencyScanner; print('Import success')"
  </verify>
  <done>
    NpmDependencyScanner class created with scan_packages, _create_package_json, _run_package_manager_audit methods
  </done>
</task>

<task type="auto">
  <name>Task 2: Add Snyk integration to NpmDependencyScanner</name>
  <files>backend/core/npm_dependency_scanner.py</files>
  <action>
    Extend NpmDependencyScanner with Snyk vulnerability checking:

    1. Implement _run_snyk_check method (RESEARCH.md lines 362-420):
       ```python
       def _run_snyk_check(self, working_dir: str) -> Dict[str, Any]:
           try:
               cmd = ["snyk", "test", "--json", "--severity-threshold=medium"]
               result = subprocess.run(cmd, cwd=working_dir, capture_output=True, text=True, timeout=120, env={**os.environ, "SNYK_API_KEY": self.snyk_api_key})
               # Parse vulnerabilities from JSON output
           except subprocess.TimeoutExpired:
               return {"vulnerabilities": []}
       ```

    2. Update scan_packages to call both npm audit and Snyk:
       - Merge vulnerability lists from both sources
       - Return combined results

    3. Handle Snyk not installed gracefully:
       - Check if snyk command exists
       - Skip Snyk if not available (log warning)

    4. Add environment variable check:
       - Only run Snyk if SNYK_API_KEY is set

    CRITICAL: Snyk is optional - scanner works with npm audit only
  </action>
  <verify>
    grep -n "_run_snyk_check\|snyk" /Users/rushiparikh/projects/atom/backend/core/npm_dependency_scanner.py
  </verify>
  <done>
    Snyk integration added with optional API key support, graceful fallback when unavailable
  </done>
</task>

<task type="auto">
  <name>Task 3: Create NpmScriptAnalyzer for postinstall threat detection</name>
  <files>backend/core/npm_script_analyzer.py</files>
  <action>
    Create NpmScriptAnalyzer class following RESEARCH.md Pattern 4:

    1. Create file with imports:
       - re, json, logging, requests
       - typing: Any, Dict, List, Optional

    2. Define malicious patterns regex list (RESEARCH.md lines 617-641):
       - Network exfiltration: r'\bfetch\s*\(', r'\baxios\s*\.', r'\bhttps?\.'
       - Credential theft: r'\bprocess\.env\.', r'\bfs\.readFileSync\s*\('
       - Command execution: r'\brequire\s*\(\s*["\']child_process["\']', r'\bexec\s*\('
       - Dynamic code: r'\beval\s*\(', r'\bFunction\s*\('
       - Obfuscation: r'\batob\s*\('

    3. Define suspicious combinations list (RESEARCH.md lines 644-648):
       - trufflehog + axios = credential exfiltration
       - dotenv + axios = API key theft

    4. Implement analyze_package_scripts method:
       - Fetch package metadata from npm registry API
       - Extract postinstall, preinstall, install scripts
       - Match script content against malicious patterns
       - Return {"malicious": bool, "warnings": List, "scripts_found": List}

    5. Implement _fetch_package_info method:
       - GET https://registry.npmjs.org/{package_name}
       - Parse JSON for latest version
       - Return scripts dict

    CRITICAL: Detect Shai-Hulud/Sha1-Hulud attack patterns from RESEARCH.md
  </action>
  <verify>
    python -c "from backend.core.npm_script_analyzer import NpmScriptAnalyzer; print('Import success')"
  </verify>
  <done>
    NpmScriptAnalyzer detects malicious postinstall patterns, suspicious package combinations
  </done>
</task>

<task type="auto">
  <name>Task 4: Create tests for NpmDependencyScanner</name>
  <files>backend/tests/test_npm_dependency_scanner.py</files>
  <action>
    Create comprehensive test file for NpmDependencyScanner:

    1. Test file setup:
       - Import pytest, NpmDependencyScanner
       - Mock subprocess.run for npm audit commands
       - Mock tempfile operations

    2. Test cases:
       - test_scan_packages_empty: Empty package list returns safe=True
       - test_scan_packages_with_vulnerabilities: Mock npm audit JSON with vulnerabilities
       - test_npm_audit_timeout: Timeout returns safe=True with warning
       - test_create_package_json: Validates package.json structure
       - test_yarn_package_manager: yarn audit --json support
       - test_pnpm_package_manager: pnpm audit --json support
       - test_snyk_integration: Snyk check when API key provided
       - test_snyk_not_available: Graceful skip when snyk not installed
       - test_vulnerability_parsing: Correct JSON parsing from npm audit

    3. Mock patterns:
       - Use pytest.mock.patch for subprocess.run
       - Mock npm audit JSON output from RESEARCH.md

    4. Performance assertions:
       - Assert scan completes <120s (timeout)
       - Assert returned dict structure matches spec

    Use pytest fixtures for scanner instance and temp directory.
  </action>
  <verify>
    pytest backend/tests/test_npm_dependency_scanner.py -v --collect-only | grep "test_"
  </verify>
  <done>
    9+ test cases covering npm audit, yarn/pnpm, Snyk, timeout handling, vulnerability parsing
  </done>
</task>

<task type="auto">
  <name>Task 5: Create tests for NpmScriptAnalyzer</name>
  <files>backend/tests/test_npm_script_analyzer.py</files>
  <action>
    Create comprehensive test file for NpmScriptAnalyzer:

    1. Test file setup:
       - Import pytest, NpmScriptAnalyzer
       - Mock requests.get for npm registry API

    2. Test cases:
       - test_analyze_no_scripts: Package without scripts returns safe
       - test_analyze_postinstall_safe: Legitimate postinstall passes
       - test_detect_fetch_pattern: Detects network exfiltration
       - test_detect_process_env: Detects credential theft
       - test_detect_child_process: Detects command execution
       - test_detect_eval: Detects dynamic code execution
       - test_suspicious_combination: Detects trufflehog+axios
       - test_fetch_package_info: Npm registry API integration
       - test_malicious_flag_set: Sets malicious=True on critical patterns

    3. Mock data:
       - Mock npm registry responses for various packages
       - Include Shai-Hulud attack scenario (TruffleHog script)

    4. Security assertions:
       - All malicious patterns detected
       - No false negatives on critical threats
       - Warnings list populated correctly

    Use pytest.mark.parametrize for multiple pattern tests.
  </action>
  <verify>
    pytest backend/tests/test_npm_script_analyzer.py -v --collect-only | grep "test_"
  </verify>
  <done>
    9+ test cases covering script analysis, malicious patterns, suspicious combinations, registry API
  </done>
</task>

</tasks>

<verification>
Overall phase verification:
1. NpmDependencyScanner scans packages with npm audit
2. Snyk integration works when API key provided, skips gracefully when not
3. NpmScriptAnalyzer detects all malicious patterns from RESEARCH.md
4. Timeout handling returns safe=True (doesn't block on scanner failure)
5. All tests pass: pytest backend/tests/test_npm_dependency_scanner.py backend/tests/test_npm_script_analyzer.py -v
</verification>

<success_criteria>
1. NpmDependencyScanner.scan_packages returns vulnerability list from npm audit
2. Snyk check runs when SNYK_API_KEY set, adds vulnerabilities to results
3. NpmScriptAnalyzer.analyze_package_scripts detects fetch, child_process, process.env, eval patterns
4. Suspicious package combinations flagged (trufflehog+axios, dotenv+axios)
5. Timeout handling prevents blocking on scanner failures
6. 18+ tests covering all scanner and analyzer methods
</success_criteria>

<output>
After completion, create `.planning/phases/36-npm-package-support/36-npm-package-support-02-SUMMARY.md`
</output>
