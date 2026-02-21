---
phase: 36-npm-package-support
plan: 05
type: execute
wave: 3
depends_on: [36-npm-package-support-01, 36-npm-package-support-02, 36-npm-package-support-03]
files_modified:
  - backend/tests/test_npm_security_escape.py
  - backend/tests/test_npm_security_resource_exhaustion.py
  - backend/tests/test_npm_security_typosquatting.py
  - backend/tests/test_npm_security_supply_chain.py
autonomous: true

must_haves:
  truths:
    - "Container escape tests validate Docker isolation (no host access)"
    - "Resource exhaustion tests enforce memory and CPU limits"
    - "Typosquatting tests detect malicious package name variants"
    - "Supply chain tests block Shai-Hulud style postinstall attacks"
    - "All security tests pass with documented threat scenarios"
  artifacts:
    - path: backend/tests/test_npm_security_escape.py
      contains: test_no_docker_socket_access, test_no_host_filesystem, test_no_privileged_mode
    - path: backend/tests/test_npm_security_resource_exhaustion.py
      contains: test_memory_limit_enforced, test_cpu_limit_enforced, test_timeout_enforced
    - path: backend/tests/test_npm_security_typosquatting.py
      contains: test_typosquatting_detection, test_slopsquatting_detection
    - path: backend/tests/test_npm_security_supply_chain.py
      contains: test_shai_hulud_attack_blocked, test_postinstall_scripts_blocked
  key_links:
    - from: backend/tests/test_npm_security_escape.py
      to: backend/core/skill_sandbox.py
      via: execute_nodejs security constraints
      pattern: network_disabled=True.*read_only=True
    - from: backend/tests/test_npm_security_typosquatting.py
      to: backend/core/npm_script_analyzer.py
      via: package name validation
      pattern: typosquatting|slopsquatting
---

<objective>
Create comprehensive security tests validating npm package isolation, resource limits, supply chain attacks, and common npm threat scenarios.

**Purpose:** Ensure npm package sandboxing prevents container escape, resource exhaustion, typosquatting, and postinstall script attacks (Shai-Hulud/Sha1-Hulud).

**Output:** Four security test files with 25+ tests covering all npm threat vectors from RESEARCH.md Pitfalls section.

</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/phases/36-npm-package-support/36-RESEARCH.md
@backend/core/skill_sandbox.py (execute_nodejs method)
@backend/core/npm_script_analyzer.py (threat detection)
@backend/core/npm_package_installer.py (Docker isolation)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create container escape security tests</name>
  <files>backend/tests/test_npm_security_escape.py</files>
  <action>
    Create security test file for container escape scenarios:

    1. Test file setup:
       - Import pytest, HazardSandbox
       - Mock Docker client for escape scenario simulation

    2. Test cases:
       - test_no_docker_socket_access:
         - Try to access /var/run/docker.sock from Node.js code
         - Assert file not found error (socket not mounted)

       - test_no_host_filesystem_access:
         - Try to read /etc/passwd or /host filesystem
         - Assert path doesn't exist or access denied

       - test_no_privileged_mode:
         - Verify container never runs with --privileged flag
         - Check for --cap-drop=ALL in container config

       - test_no_network_access:
         - Try fetch('https://example.com') from Node.js
         - Assert network error (ECONNREFUSED)

       - test_readonly_filesystem:
         - Try to write to /skill or /app directory
         - Assert EROFS (read-only filesystem) error

       - test_tmpfs_only_writeable:
         - Try to write to /tmp (should succeed)
         - Try to write to /root (should fail)

       - test_non_root_user:
         - Check process.getuid() in Node.js
         - Assert uid=1001 (nodejs user, not 0)

       - test_no_sys_modules_access:
         - Try to require('fs') to access /sys/kernel
         - Assert permission denied

    3. Security assertions:
       - All escape attempts fail with appropriate errors
       - Container configuration validated for security constraints

    Reference: RESEARCH.md Pitfall 4 "Container Escape via Node.js Packages"
  </action>
  <verify>
    pytest backend/tests/test_npm_security_escape.py -v --collect-only | grep "test_" | wc -l
  </verify>
  <done>
    8+ test cases covering Docker socket, filesystem, privileged mode, network, read-only enforcement
  </done>
</task>

<task type="auto">
  <name>Task 2: Create resource exhaustion security tests</name>
  <files>backend/tests/test_npm_security_resource_exhaustion.py</files>
  <action>
    Create security test file for resource exhaustion attacks:

    1. Test file setup:
       - Import pytest, HazardSandbox
       - Mock Docker client for resource monitoring

    2. Test cases:
       - test_memory_limit_enforced:
         - Run Node.js code that allocates large arrays
         - Verify container killed when exceeding limit (256m default)

       - test_cpu_limit_enforced:
         - Run CPU-intensive code (infinite loop)
         - Verify container throttled after quota (0.5 cores default)

       - test_timeout_enforced:
         - Run infinite loop with 5s timeout
         - Verify container killed after timeout

       - test_fork_bomb_prevented:
         - Try to spawn child processes recursively
         - Verify --pids-limit prevents fork bomb

       - test_file_descriptor_limit:
         - Try to open many files
         - Verify ulimit enforced

       - test_no_swap_usage:
         - Try to exhaust memory to trigger swap
         - Verify --memory-swap limit prevents swap

       - test_disk_write_limit:
         - Try to write large files to /tmp
         - Verify tmpfs size limit enforced

       - test_concurrent_execution_limits:
         - Run multiple containers simultaneously
         - Verify host resources not exhausted

    3. Security assertions:
       - All resource limits enforced
       - Host system remains responsive

    Reference: RESEARCH.md Pitfall 5 "Resource Exhaustion Attacks"
  </action>
  <verify>
    pytest backend/tests/test_npm_security_resource_exhaustion.py -v --collect-only | grep "test_" | wc -l
  </verify>
  <done>
    8+ test cases covering memory, CPU, timeout, fork bombs, file descriptors, swap, disk limits
  </done>
</task>

<task type="auto">
  <name>Task 3: Create typosquatting detection tests</name>
  <files>backend/tests/test_npm_security_typosquatting.py</files>
  <action>
    Create security test file for typosquatting attacks:

    1. Test file setup:
       - Import pytest, NpmScriptAnalyzer
       - Mock npm registry API responses

    2. Test cases:
       - test_typosquatting_detection_exprss_vs_express:
         - Detect "exprss" as typosquatting for "express"
         - Verify package flagged as suspicious

       - test_typosquatting_detection_lodas_vs_lodash:
         - Detect "lodas" as typosquatting for "lodash"
         - Verify package flagged

       - test_slopsquatting_detection_ai_hallucinated_packages:
         - Detect AI-recommended non-existent packages
         - Example: "unusued-imports" vs "eslint-plugin-unused-imports"

       - test_new_package_low_downloads_flagged:
         - Flag package created <6 months ago with <1000 downloads
         - Verify warning in scan results

       - test_suspicious_maintainer_account:
         - Detect new maintainer with no other packages
         - Verify account flagged for review

       - test_high_version_number_attack:
         - Flag packages with version >99.0.0 (dependency confusion)
         - Verify package blocked

       - test_legitimate_package_allowed:
         - Known good packages pass validation
         - lodash, express, react allowlisted

       - test_typosquatting_combination_attack:
         - Detect multiple typosquatting packages in one install
         - Verify all flagged

    3. Security assertions:
       - All typosquatting attempts detected
       - Legitimate packages not blocked

    Reference: RESEARCH.md Pitfall 2 "npm Typosquatting Attacks" and Pitfall 3 "Dependency Confusion"
  </action>
  <verify>
    pytest backend/tests/test_npm_security_typosquatting.py -v --collect-only | grep "test_" | wc -l
  </verify>
  <done>
    8+ test cases covering typosquatting, slopsquatting, new packages, suspicious maintainers, high versions
  </done>
</task>

<task type="auto">
  <name>Task 4: Create supply chain attack security tests</name>
  <files>backend/tests/test_npm_security_supply_chain.py</files>
  <action>
    Create security test file for supply chain attacks:

    1. Test file setup:
       - Import pytest, NpmScriptAnalyzer, NpmDependencyScanner
       - Mock npm registry, npm audit, Snyk responses

    2. Test cases:
       - test_shai_hulud_attack_blocked:
         - Simulate TruffleHog postinstall script
         - Verify malicious=True, installation blocked

       - test_sha1_hulud_second_wave_blocked:
         - Simulate preinstall with Bun runtime installation
         - Verify preinstall scripts also detected

       - test_postinstall_scripts_blocked_by_default:
         - Any package with postinstall script blocked
         - Even if pattern not recognized

       - test_credential_exfiltration_detected:
         - Detect process.env + fetch combination
         - Flag as credential theft

       - test_command_execution_detected:
         - Detect child_process.spawn usage
         - Flag as command execution threat

       - test_base64_obfuscation_detected:
         - Detect atob() with suspicious arguments
         - Flag as obfuscated payload

       - test_eval_code_execution_detected:
         - Detect eval() with dynamic content
         - Flag as code execution threat

       - test_npm_audit_cve_detection:
         - Mock npm audit returning CVE
         - Verify vulnerability in scan results

       - test_snyk_vulnerability_detection:
         - Mock Snyk returning vulnerabilities
         - Verify merged with npm audit results

       - test_package_json_tampering_detected:
         - Detect modified package.json hash
         - Verify lockfile validation fails

    3. Security assertions:
       - All Shai-Hulud variants blocked
       - CVEs detected by npm audit
       - Snyk provides additional vulnerability coverage

    Reference: RESEARCH.md Pitfall 1 "Postinstall Script Malware (Shai-Hulud/Sha1-Hulud)"
  </action>
  <verify>
    pytest backend/tests/test_npm_security_supply_chain.py -v --collect-only | grep "test_" | wc -l
  </verify>
  <done>
    10+ test cases covering Shai-Hulud, postinstall scripts, credential theft, CVEs, Snyk, lockfile tampering
  </done>
</task>

</tasks>

<verification>
Overall phase verification:
1. All container escape attempts fail with appropriate errors
2. All resource limits enforced (memory, CPU, timeout)
3. Typosquatting packages detected and flagged
4. Supply chain attacks (Shai-Hulud, postinstall) blocked
5. All security tests pass: pytest backend/tests/test_npm_security_*.py -v
</verification>

<success_criteria>
1. 8+ container escape tests (Docker socket, filesystem, privileged mode, network)
2. 8+ resource exhaustion tests (memory, CPU, timeout, fork bombs)
3. 8+ typosquatting tests (exprss, lodas, slopsquatting, new packages)
4. 10+ supply chain tests (Shai-Hulud, postinstall, CVEs, Snyk, lockfile)
5. 34+ total security tests covering all RESEARCH.md Pitfalls
6. All threat scenarios documented with mitigation
</success_criteria>

<output>
After completion, create `.planning/phases/36-npm-package-support/36-npm-package-support-05-SUMMARY.md`
</output>
