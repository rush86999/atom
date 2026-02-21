---
phase: 36-npm-package-support
plan: 07
type: execute
wave: 4
depends_on: [36-npm-package-support-01, 36-npm-package-support-02, 36-npm-package-support-03, 36-npm-package-support-04, 36-npm-package-support-05, 36-npm-package-support-06]
files_modified:
  - docs/NPM_PACKAGE_SUPPORT.md
  - docs/SKILL_FORMAT.md
  - backend/tests/README_NPM_TESTS.md
autonomous: true

must_haves:
  truths:
    - "NPM_PACKAGE_SUPPORT.md documents npm package installation and governance"
    - "SKILL_FORMAT.md updated with node_packages field documentation"
    - "README_NPM_TESTS.md explains npm security test scenarios"
    - "All docs include npm-specific examples (lodash, express, etc.)"
    - "Security threats from RESEARCH.md documented with mitigations"
  artifacts:
    - path: docs/NPM_PACKAGE_SUPPORT.md
      contains: npm package governance, installation, security, API reference
    - path: docs/SKILL_FORMAT.md
      contains: node_packages field, package_manager, npm examples
    - path: backend/tests/README_NPM_TESTS.md
      contains: security test scenarios, threat mitigations
  key_links:
    - from: docs/NPM_PACKAGE_SUPPORT.md
      to: backend/core/npm_package_installer.py
      via: installation workflow documentation
      pattern: install_packages.*npm
    - from: docs/SKILL_FORMAT.md
      to: backend/core/skill_parser.py
      via: node_packages parsing documentation
      pattern: parse_node_packages
---

<objective>
Create comprehensive documentation for npm package support, including usage guide, security considerations, API reference, and test documentation.

**Purpose:** Document npm package installation, governance, security, and SKILL.md format for users and developers extending the npm package system.

**Output:** NPM_PACKAGE_SUPPORT.md user guide, updated SKILL_FORMAT.md with npm examples, README_NPM_TESTS.md security test documentation.

</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/phases/36-npm-package-support/36-RESEARCH.md
@backend/core/npm_package_installer.py (implementation)
@backend/core/npm_script_analyzer.py (security)
@backend/api/package_routes.py (API endpoints)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create NPM_PACKAGE_SUPPORT.md user guide</name>
  <files>docs/NPM_PACKAGE_SUPPORT.md</files>
  <action>
    Create comprehensive user guide for npm package support:

    1. Document overview (500+ words):
       - What npm package support is
       - Why it's needed (matching OpenClaw capabilities)
       - Security model (Docker isolation, governance checks)

    2. Document governance (300+ words):
       - Maturity-based permissions (STUDENT blocked, INTERN+ approved)
       - Whitelist/blocklist system
       - Cache performance (<1ms lookups)
       - Example: Checking npm package permission

    3. Document installation workflow (500+ words):
       - Step-by-step npm package installation
       - Docker image building per skill
       - node_modules isolation
       - package_manager options (npm, yarn, pnpm)
       - Code examples for each package manager

    4. Document security (400+ words):
       - postinstall script blocking (--ignore-scripts)
       - Vulnerability scanning (npm audit + Snyk)
       - Threat scenarios (Shai-Hulud, typosquatting)
       - Security best practices

    5. Document API endpoints (300+ words):
       - Governance: /api/packages/npm/check, /api/packages/npm/request
       - Installation: /api/packages/npm/install
       - Execution: /api/packages/npm/execute
       - Request/response examples

    6. Document troubleshooting (200+ words):
       - Common errors and solutions
       - Debug tips
       - Where to find logs

    Include code examples with lodash, express, axios packages.
  </action>
  <verify>
    wc -l /Users/rushiparikh/projects/atom/docs/NPM_PACKAGE_SUPPORT.md && grep -c "##\|###" /Users/rushiparikh/projects/atom/docs/NPM_PACKAGE_SUPPORT.md
  </verify>
  <done>
    NPM_PACKAGE_SUPPORT.md created with 6+ sections, 2200+ words, code examples
  </done>
</task>

<task type="auto">
  <name>Task 2: Update SKILL_FORMAT.md with npm package documentation</name>
  <files>docs/SKILL_FORMAT.md</files>
  <action>
    Update SKILL_FORMAT.md to document node_packages field:

    1. Add "npm Packages" section after "Python Packages":
       ```markdown
       ## npm Packages

       Skills can declare Node.js dependencies using the `node_packages` field:

       ```yaml
       ---
       name: "HTTP Request Skill"
       description: "Make HTTP requests using Node.js"
       node_packages:
         - axios@^1.6.0
         - lodash@4.17.21
       package_manager: npm  # Optional: npm (default), yarn, or pnpm
       ---

       const axios = require('axios');
       const _ = require('lodash');

       async function makeRequest(url) {
         const response = await axios.get(url);
         return _.get(response, 'data', {});
       }

       makeRequest(inputs.url || 'https://api.example.com');
       ```

       ### Package Manager Options

       - **npm** (default): Standard Node.js package manager
       - **yarn**: Faster installs, PnP mode support
       - **pnpm**: Strict dependency isolation (highest security)

       ### Version Ranges

       npm packages support semantic versioning ranges:
       - `axios@1.6.0` - Exact version
       - `axios@^1.6.0` - Compatible with version 1.6.0 and above
       - `axios@~1.6.0` - Patch updates only
       ```

    2. Add governance section for npm packages:
       - STUDENT agents blocked from npm packages
       - INTERN+ agents require approval
       - Banned packages blocked for all

    3. Add security considerations:
       - postinstall scripts blocked by default
       - Vulnerability scanning before installation
       - Shai-Hulud attack protection

    4. Update examples section with npm skill example

    CRITICAL: Match OpenClaw SKILL.md format for compatibility
  </action>
  <verify>
    grep -n "node_packages\|npm Packages" /Users/rushiparikh/projects/atom/docs/SKILL_FORMAT.md
  </verify>
  <done>
    SKILL_FORMAT.md updated with npm packages section, package_manager options, security notes
  </done>
</task>

<task type="auto">
  <name>Task 3: Create README_NPM_TESTS.md for security test documentation</name>
  <files>backend/tests/README_NPM_TESTS.md</files>
  <action>
    Create security test documentation:

    1. Document test file structure:
       - test_npm_security_escape.py - Container escape tests
       - test_npm_security_resource_exhaustion.py - Resource limit tests
       - test_npm_security_typosquatting.py - Typosquatting detection tests
       - test_npm_security_supply_chain.py - Supply chain attack tests

    2. Document each threat scenario (RESEARCH.md Pitfalls):
       - Threat name
       - How it works
       - Test scenario
       - Mitigation strategy

    3. Example documentation format:
       ```markdown
       ### Container Escape Tests

       **Threat:** Malicious npm package attempts to escape Docker container to access host system.

       **Test:** `test_no_docker_socket_access` in test_npm_security_escape.py

       **How it works:** Package tries to access /var/run/docker.sock to control host containers.

       **Mitigation:**
       - Never mount /var/run/docker.sock
       - Always use network_disabled=True
       - Always use read_only=True
       - Run as non-root user (nodejs, uid=1001)

       **Run test:**
       ```bash
       pytest backend/tests/test_npm_security_escape.py::test_no_docker_socket_access -v
       ```
       ```

    4. Document all 8+ container escape scenarios

    5. Document all 8+ resource exhaustion scenarios

    6. Document all 8+ typosquatting scenarios

    7. Document all 10+ supply chain scenarios

    Include threat reference links to RESEARCH.md.
  </action>
  <verify>
    wc -l /Users/rushiparikh/projects/atom/backend/tests/README_NPM_TESTS.md && grep -c "###" /Users/rushiparikh/projects/atom/backend/tests/README_NPM_TESTS.md
  </verify>
  <done>
    README_NPM_TESTS.md created with 34+ threat scenario documentations
  </done>
</task>

<task type="auto">
  <name>Task 4: Add quick start examples to NPM_PACKAGE_SUPPORT.md</name>
  <files>docs/NPM_PACKAGE_SUPPORT.md</files>
  <action>
    Add quick start section with practical examples:

    1. Add "Quick Start" section at beginning:
       ```markdown
       ## Quick Start

       ### Example 1: Using npm packages in a skill

       Create a SKILL.md file:

       ```yaml
       ---
       name: "Data Processing Skill"
       description: "Process data using Lodash"
       node_packages:
         - lodash@4.17.21
       ---

       const _ = require('lodash');

       function process(data) {
         return _.map(data, x => x * 2);
       }

       process(inputs.data || []);
       ```
       ```

    2. Add API usage examples:
       ```python
       # Check npm package permission
       response = requests.get("http://localhost:8000/api/packages/npm/check", params={
           "agent_id": "agent-123",
           "package_name": "lodash",
           "version": "4.17.21"
       })

       # Install npm packages
       response = requests.post("http://localhost:8000/api/packages/npm/install", json={
           "agent_id": "agent-123",
           "skill_id": "skill-456",
           "packages": ["lodash@4.17.21", "axios@^1.6.0"]
       })
       ```

    3. Add troubleshooting quick reference table:
       | Error | Cause | Solution |
       |-------|-------|----------|
       | Permission denied | STUDENT agent | Use INTERN+ maturity |
       | Malicious scripts | postinstall detected | Review package, use --ignore-scripts |
       | Vulnerabilities found | npm audit results | Update package version |

    Include curl examples for quick testing.
  </action>
  <verify>
    grep -n "Quick Start\|curl\|Example" /Users/rushiparikh/projects/atom/docs/NPM_PACKAGE_SUPPORT.md
  </verify>
  <done>
    Quick start section added with practical examples and troubleshooting table
  </done>
</task>

<task type="auto">
  <name>Task 5: Update main README with npm package reference</name>
  <files>docs/README.md</files>
  <action>
    Update main README to reference npm package support:

    1. Add npm package support to feature list:
       ```markdown
       ## Features

       - **Python Package Support**: Safe execution with governance, vulnerability scanning, sandboxing
       - **npm Package Support**: Node.js packages with Docker isolation, postinstall blocking (NEW)
       ```

    2. Add npm package link to documentation:
       ```markdown
       ## Documentation

       - [npm Package Support](docs/NPM_PACKAGE_SUPPORT.md) - Node.js packages and governance
       - [SKILL Format](docs/SKILL_FORMAT.md) - Creating skills with npm dependencies
       ```

    3. Add npm package security note:
       ```markdown
       ## Security

       Atom includes comprehensive security measures for npm packages:
       - postinstall script blocking (--ignore-scripts flag)
       - Shai-Hulud attack detection and prevention
       - Typosquatting and dependency confusion protection
       - See [NPM_PACKAGE_SUPPORT.md](docs/NPM_PACKAGE_SUPPORT.md#security) for details
       ```

    4. Update "Getting Started" with npm skill example

    Keep README concise but include links to detailed docs.
  </action>
  <verify>
    grep -n "npm\|NPM_PACKAGE_SUPPORT" /Users/rushiparikh/projects/atom/docs/README.md
  </verify>
  <done>
    Main README updated with npm package support features and documentation links
  </done>
</task>

</tasks>

<verification>
Overall phase verification:
1. NPM_PACKAGE_SUPPORT.md exists with 6+ sections, 2200+ words
2. SKILL_FORMAT.md has node_packages field documentation with examples
3. README_NPM_TESTS.md documents all 34+ security test scenarios
4. Main README references npm package support documentation
5. All docs include code examples and troubleshooting tips
</verification>

<success_criteria>
1. NPM_PACKAGE_SUPPORT.md with governance, installation, security, API sections
2. SKILL_FORMAT.md updated with node_packages field, package_manager options
3. README_NPM_TESTS.md with threat scenario documentation for all 4 security test files
4. Main README updated with npm package feature reference
5. All docs include practical examples (lodash, express, axios)
6. Documentation matches RESEARCH.md threat scenarios
</success_criteria>

<output>
After completion, create `.planning/phases/36-npm-package-support/36-npm-package-support-07-SUMMARY.md`
</output>
